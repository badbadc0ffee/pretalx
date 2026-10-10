# SPDX-FileCopyrightText: 2026-present Florian Moesch
# SPDX-License-Identifier: AGPL-3.0-only WITH LicenseRef-Pretalx-AGPL-3.0-Terms
import copy
import datetime as dt
import json

import pytest
from django.db.models import F
from django_scopes import scopes_disabled

from pretalx.event.domain.event import apply_date_edit, move_full_event, shred_event
from pretalx.orga.forms.export import ScheduleExportForm
from pretalx.person.models.auth_token import ENDPOINTS
from pretalx.schedule.domain.availability import merged_speaker_availabilities
from pretalx.schedule.domain.notifications import generate_notifications
from pretalx.schedule.domain.release import freeze_schedule
from pretalx.schedule.domain.room import annotate_room_usage, room_is_in_use
from pretalx.schedule.domain.warnings import (
    compute_warnings,
    get_all_talk_warnings,
    get_talk_warnings,
)
from pretalx.schedule.models import TalkSlot
from pretalx.submission.domain.queries.submission import (
    annotate_submission_signup_status,
)
from pretalx.submission.domain.submission import (
    apply_field_changes,
    delete_submission,
    set_wip_slot,
)
from pretalx.submission.interfaces.forms.submission import SubmissionOrgaForm
from pretalx.submission.models import Submission, SubmissionStates
from tests.factories import (
    RoomFactory,
    SpeakerFactory,
    SubmissionFactory,
    TalkSlotFactory,
    UserApiTokenFactory,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def hidden(event, talk_slot):
    submission = SubmissionFactory(
        event=event, state=SubmissionStates.CONFIRMED, is_hidden=True
    )
    TalkSlotFactory(submission=submission)
    freeze_schedule(talk_slot.schedule, "v1", notify_speakers=False)
    return submission


def test_hidden_schedule(client, event, talk_slot, hidden):
    response = client.get(event.urls.schedule_nojs)

    assert response.status_code == 200
    content = response.content.decode()
    assert talk_slot.submission.title in content
    assert hidden.title not in content
    assert client.get(hidden.urls.public).status_code == 404


@pytest.mark.parametrize("authenticated", (False, True))
def test_hidden_api(client, event, organiser_user, hidden, authenticated):
    with scopes_disabled():
        token = UserApiTokenFactory(
            user=organiser_user,
            limit_events=[event],
            endpoints=dict.fromkeys(ENDPOINTS, ["list", "retrieve"]),
        )
    headers = {"Authorization": f"Token {token.token}"} if authenticated else {}

    response = client.get(event.api_urls.submissions, headers=headers)
    assert response.status_code == 200
    assert (hidden.code in response.content.decode()) == authenticated


@pytest.mark.unit
def test_hidden_release(event, published_talk_slot):
    submission = published_talk_slot.submission
    for version, is_hidden in (("v2", True), ("v3", False)):
        previous = event.current_schedule
        submission.is_hidden = is_hidden
        submission.save(update_fields=["is_hidden"])
        apply_field_changes(submission, {"is_hidden"})
        wip = event.wip_schedule
        assert (
            wip.talks(manager="all_objects").get(submission=submission).is_visible
            is not is_hidden
        )
        assert (
            previous.talks(manager="all_objects").get(submission=submission).is_visible
            is is_hidden
        )

        # Releases also correct stale WIP visibility.
        wip.talks.filter(submission=submission).update(is_visible=is_hidden)
        released, _ = freeze_schedule(wip, version, notify_speakers=False)

        assert (
            released.talks(manager="all_objects").get(submission=submission).is_visible
            is not is_hidden
        )
        assert (
            previous.talks(manager="all_objects").get(submission=submission).is_visible
            is is_hidden
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("is_hidden", "is_featured"),
    ((False, False), (True, False), (True, True), (False, True)),
)
def test_hidden_form(event, talk_slot, is_hidden, is_featured):
    submission = talk_slot.submission
    form = SubmissionOrgaForm(
        event=event,
        instance=submission,
        data={
            "title": submission.title,
            "abstract": "Abstract",
            "submission_type": submission.submission_type_id,
            "content_locale": "en",
            "is_hidden": is_hidden,
            "is_featured": is_featured,
        },
    )

    assert form.is_valid(), form.errors
    form.save()
    talk_slot.refresh_from_db()
    assert talk_slot.is_visible is not is_hidden
    assert bool(form["is_featured"].help_text) == (is_hidden and is_featured)


def test_hidden_is_retroactive(
    client, event, published_talk_slot, django_capture_on_commit_callbacks
):
    delta = dt.timedelta(hours=1)
    with scopes_disabled():
        # v2 adds a new session, v3 moves the one from v1
        added = SubmissionFactory(event=event, state=SubmissionStates.CONFIRMED)
        TalkSlotFactory(submission=added)
        freeze_schedule(event.wip_schedule, "v2", notify_speakers=False)
        moved = published_talk_slot.submission
        event.wip_schedule.talks.filter(submission=moved).update(
            start=F("start") + delta, end=F("end") + delta
        )
        freeze_schedule(event.wip_schedule, "v3", notify_speakers=False)

    def set_hidden(submission, is_hidden):
        with scopes_disabled(), django_capture_on_commit_callbacks(execute=True):
            submission.is_hidden = is_hidden
            submission.save(update_fields=["is_hidden"])
            apply_field_changes(submission, {"is_hidden"})

    # Each session is listed in the changelog entry of the release that changed it.
    for submission, version in ((added, "v2"), (moved, "v3")):
        urls = (
            event.urls.schedule_nojs,
            f"{event.urls.changelog}{version}/",
            submission.urls.public,
        )
        for url in urls:
            assert submission.title in client.get(url).content.decode()

        set_hidden(submission, True)
        for url in urls[:2]:
            assert submission.title not in client.get(url).content.decode()
        assert client.get(submission.urls.public).status_code == 404

        set_hidden(submission, False)
        for url in urls:
            assert submission.title in client.get(url).content.decode()


def test_hidden_form_shows_schedule(event, talk_slot):
    submission = talk_slot.submission
    with scopes_disabled():
        submission.is_hidden = True
        submission.save(update_fields=["is_hidden"])
        apply_field_changes(submission, {"is_hidden"})
        form = SubmissionOrgaForm(event=event, instance=submission)

        assert form.initial["room"] == talk_slot.room
        assert form.initial["start"] == talk_slot.local_start
        assert form.initial["end"] == talk_slot.local_end


def test_hidden_slot_in_schedule_editor(client, event, organiser_user, hidden):
    client.force_login(organiser_user)
    with scopes_disabled():
        slot = event.wip_schedule.talks(manager="all_objects").get(submission=hidden)
        new_start = slot.start + dt.timedelta(hours=2)
    url = f"{event.orga_urls.schedule_api}talks/{slot.pk}/"

    response = client.patch(
        url,
        data=json.dumps({"start": new_start.isoformat(), "room": slot.room_id}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["is_hidden"] is True
    with scopes_disabled():
        slot.refresh_from_db()
        assert slot.start == new_start

    response = client.patch(url, data="{}", content_type="application/json")
    assert response.status_code == 200
    with scopes_disabled():
        slot.refresh_from_db()
        assert slot.start is None


def test_hidden_slot_quick_schedule(client, event, organiser_user, hidden):
    client.force_login(organiser_user)
    with scopes_disabled():
        slot = event.wip_schedule.talks(manager="all_objects").get(submission=hidden)
        slot.start = slot.end = slot.room = None
        slot.save()
        room = RoomFactory(event=event)

    response = client.post(
        f"{event.orga_urls.schedule}quick/{hidden.code}/",
        data={
            "start_date": event.date_from.strftime("%Y-%m-%d"),
            "start_time": "10:00:00",
            "room": room.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    with scopes_disabled():
        slot.refresh_from_db()
        assert slot.room_id == room.pk
        assert slot.start.date() == event.date_from


def test_hidden_slot_counts_in_schedule_warnings(event, talk_slot):
    schedule = talk_slot.schedule
    with scopes_disabled():
        submission = SubmissionFactory(
            event=event, state=SubmissionStates.CONFIRMED, is_hidden=True
        )
        overlapping = TalkSlotFactory(
            submission=submission,
            schedule=schedule,
            room=talk_slot.room,
            start=talk_slot.start,
            end=talk_slot.end,
        )
        unscheduled = TalkSlotFactory(
            submission=SubmissionFactory(
                event=event, state=SubmissionStates.CONFIRMED, is_hidden=True
            ),
            schedule=schedule,
            room=None,
            start=None,
            end=None,
        )

        warnings = get_all_talk_warnings(schedule)
        assert {w["type"] for w in warnings[talk_slot]} >= {"room_overlap"}
        assert {w["type"] for w in warnings[overlapping]} >= {"room_overlap"}
        assert {w["type"] for w in get_talk_warnings(schedule, talk_slot)} >= {
            "room_overlap"
        }
        assert compute_warnings(schedule)["unscheduled"] == 1
        assert {overlapping.pk, unscheduled.pk} <= set(
            merged_speaker_availabilities(schedule)
        )


def test_hidden_slot_keeps_room_in_use(event, talk_slot):
    with scopes_disabled():
        room = RoomFactory(event=event)
        TalkSlotFactory(
            submission=SubmissionFactory(
                event=event, state=SubmissionStates.CONFIRMED, is_hidden=True
            ),
            schedule=talk_slot.schedule,
            room=room,
            start=talk_slot.start,
            end=talk_slot.end,
        )

        assert room_is_in_use(room)
        assert not room.is_deletable
        annotated = annotate_room_usage(event.rooms.filter(pk=room.pk), event).get()
        assert annotated.has_slots
        assert annotated.has_scheduled_slots
        assert annotated.is_in_use
        assert not annotated.is_deletable


def test_hidden_slot_moves_with_event(event, hidden):
    with scopes_disabled():
        slots = TalkSlot.all_objects.filter(schedule__event=event, submission=hidden)
        assert slots.count() == 2  # released v1 and WIP
        before = {slot.pk: slot.start for slot in slots}

        move_full_event(event, event.date_from + dt.timedelta(days=3))

        after = {slot.pk: slot.start for slot in slots.all()}
        assert after == {
            pk: start + dt.timedelta(days=3) for pk, start in before.items()
        }


def test_hidden_slot_is_descheduled_when_event_shrinks(event, hidden):
    with scopes_disabled():
        slot = event.wip_schedule.talks(manager="all_objects").get(submission=hidden)
        old_event = copy.copy(event)
        old_event.date_to = event.date_to + dt.timedelta(days=5)
        slot.start = event.datetime_to + dt.timedelta(days=1)
        slot.end = slot.start + dt.timedelta(hours=1)
        slot.save()

        apply_date_edit(event, old_event)

        slot.refresh_from_db()
        assert slot.start is None


def test_hidden_slot_is_deleted_with_event(event, hidden):
    with scopes_disabled():
        event_pk = event.pk
        shred_event(event)

        assert not TalkSlot.all_objects.filter(schedule__event_id=event_pk).exists()


def test_hidden_slots_are_deleted_with_submission(event, published_talk_slot):
    submission = published_talk_slot.submission
    with scopes_disabled():
        submission.is_hidden = True
        submission.save(update_fields=["is_hidden"])
        apply_field_changes(submission, {"is_hidden"})
        freeze_schedule(event.wip_schedule, "v2", notify_speakers=False)
        slots = TalkSlot.all_objects.filter(
            schedule__event=event, submission=submission
        )
        assert slots.count() == 3  # v1, v2 and the WIP schedule

        delete_submission(submission)

        assert not slots.exists()


def test_hidden_slots_with_prefetched_submission(event, published_talk_slot):
    # A prefetch through the default manager must not hide slots from domain code
    def hidden_submission():
        return (
            Submission.objects.select_related("event")
            .prefetch_related("slots")
            .get(pk=published_talk_slot.submission_id)
        )

    with scopes_disabled():
        Submission.objects.filter(pk=published_talk_slot.submission_id).update(
            is_hidden=True
        )
        wip_slot = event.wip_schedule.talks(manager="all_objects").get(
            submission_id=published_talk_slot.submission_id
        )
        assert wip_slot.start

        set_wip_slot(hidden_submission(), room=None, start=None, end=None)
        wip_slots = event.wip_schedule.talks(manager="all_objects").filter(
            submission_id=published_talk_slot.submission_id
        )
        assert wip_slots.count() == 1  # a bare slot replaces the scheduled one
        assert wip_slots.get().start is None
        assert not wip_slots.filter(pk=wip_slot.pk).exists()

        delete_submission(hidden_submission())
        assert not TalkSlot.all_objects.filter(
            submission_id=published_talk_slot.submission_id
        ).exists()


def test_hidden_speakers_get_no_schedule_mail_on_first_release(event, talk_slot):
    with scopes_disabled():
        submission = SubmissionFactory(
            event=event, state=SubmissionStates.CONFIRMED, is_hidden=True
        )
        submission.speakers.add(SpeakerFactory(event=event))
        TalkSlotFactory(submission=submission, schedule=talk_slot.schedule)
        released, _ = freeze_schedule(event.wip_schedule, "v1", notify_speakers=False)

        assert set(released.speakers_concerned) == set(
            talk_slot.submission.speakers.all()
        )
        assert len(generate_notifications(released)) == 1


def test_hidden_speakers_get_no_schedule_mail_on_later_release(event, hidden):
    with scopes_disabled():
        hidden.speakers.add(SpeakerFactory(event=event))
        slot = event.wip_schedule.talks(manager="all_objects").get(submission=hidden)
        slot.start += dt.timedelta(hours=2)
        slot.end += dt.timedelta(hours=2)
        slot.save()
        released, _ = freeze_schedule(event.wip_schedule, "v2", notify_speakers=False)

        assert released.speakers_concerned == {}
        assert generate_notifications(released) == []


def test_unhidden_speakers_get_schedule_mail_with_next_release(
    event, hidden, django_capture_on_commit_callbacks
):
    with scopes_disabled():
        speaker = SpeakerFactory(event=event)
        hidden.speakers.add(speaker)
        freeze_schedule(event.wip_schedule, "v2", notify_speakers=False)
        hidden.is_hidden = False
        hidden.save(update_fields=["is_hidden"])
        apply_field_changes(hidden, {"is_hidden"})
        released, _ = freeze_schedule(event.wip_schedule, "v3", notify_speakers=False)

        assert set(released.speakers_concerned) == {speaker}


def test_hidden_slot_in_organiser_export(event, organiser_user, hidden):
    with scopes_disabled():
        slot = (
            event.current_schedule.talks(manager="all_objects")
            .select_related("room")
            .get(submission=hidden)
        )
        form = ScheduleExportForm(event=event, user=organiser_user)
        data = form.get_data(
            event.submissions.filter(pk=hidden.pk), ["room", "start"], []
        )

    assert data == [
        {
            "ID": hidden.code,
            str(form.fields["room"].label): slot.room.name,
            str(form.fields["start"].label): slot.start.astimezone(
                event.tz
            ).isoformat(),
        }
    ]


def test_hidden_slot_id_suffix(event, hidden):
    with scopes_disabled():
        event.feature_flags["present_multiple_times"] = True
        event.save(update_fields=["feature_flags"])
        slot = (
            TalkSlot.all_objects.filter(submission=hidden)
            .select_related("schedule__event", "submission__event")
            .first()
        )

        assert slot.id_suffix == ""


def test_hidden_slot_in_delete_warning(
    client, event, organiser_user, published_talk_slot
):
    submission = published_talk_slot.submission
    with scopes_disabled():
        submission.is_hidden = True
        submission.save(update_fields=["is_hidden"])
    client.force_login(organiser_user)

    response = client.get(submission.orga_urls.delete)

    assert response.status_code == 200
    assert "All its schedule slots will also be deleted" in response.content.decode()


def test_hidden_slot_signup_capacity(event, hidden):
    with scopes_disabled():
        slot = (
            event.current_schedule.talks(manager="all_objects")
            .select_related("room")
            .get(submission=hidden)
        )
        slot.room.capacity = 42
        slot.room.save()
        annotated = annotate_submission_signup_status(
            event.submissions.filter(pk=hidden.pk), event.current_schedule
        ).get()

        assert annotated._annotated_signup_capacity == 42


def test_hidden_orga(client, event, organiser_user, hidden):
    client.force_login(organiser_user)
    for value in ("true", "false"):
        response = client.get(event.orga_urls.submissions, {"is_hidden": value})
        assert response.status_code == 200
        content = response.content.decode()
        assert (hidden.title in content) == (value == "true")
        assert ("fa-eye-slash" in content) == (value == "true")
    response = client.get(f"/orga/event/{event.slug}/schedule/api/talks/")
    assert response.status_code == 200
    talk = next(t for t in response.json()["talks"] if t["code"] == hidden.code)
    assert talk["is_hidden"] is True
    with scopes_disabled():
        form = ScheduleExportForm(event=event, user=organiser_user)
        data = form.get_data(event.submissions.filter(pk=hidden.pk), ["is_hidden"], [])
    assert data == [{"ID": hidden.code, str(form.fields["is_hidden"].label): True}]


def test_hidden_public_exceptions(client, event, hidden):
    with scopes_disabled():
        event.feature_flags.update(
            show_featured="always", submission_public_review=True
        )
        event.save(update_fields=["feature_flags"])
        hidden.is_featured = True
        hidden.save(update_fields=["is_featured"])

    for url in (event.urls.featured, hidden.urls.public, hidden.urls.review):
        response = client.get(url)
        assert response.status_code == 200
        assert hidden.title in response.content.decode()
