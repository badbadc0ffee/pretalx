# SPDX-FileCopyrightText: 2017-present Tobias Kunze
# SPDX-License-Identifier: AGPL-3.0-only WITH LicenseRef-Pretalx-AGPL-3.0-Terms

import random
from abc import ABCMeta

from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

_phrase_book = {}


class PhrasesMetaClass(ABCMeta):  # noqa
    def __new__(cls, class_name, bases, namespace, app):
        new = super().__new__(cls, class_name, bases, namespace)
        _phrase_book[app] = new()
        return new

    def __init__(cls, *args, app, **kwargs):
        super().__init__(*args, **kwargs)


class Phrases(metaclass=PhrasesMetaClass, app=""):
    def __getattribute__(self, attribute):
        result = super().__getattribute__(attribute)
        if isinstance(result, (list, tuple)):
            return random.choice(result)
        return result


class PhraseBook:
    def __getattribute__(self, attribute):
        return _phrase_book.get(attribute)


phrases = PhraseBook()


class BasePhrases(Phrases, app="base"):
    """This class contains base phrases that are guaranteed to remain the same
    (i.e., are not randomly chosen).

    They are still provided as a list to make it possible to combine
    them with new phrases in other classes.
    """

    # Translators: This is the label on buttons that trigger the sending of emails.
    send = _("Send")
    # Translators: This is the label on save buttons.
    save = _("Save")
    cancel = _("Cancel")
    # Translators: This is the label on edit buttons.
    edit = _("Edit")
    all_choices = _("all")
    # Translators: This is a label on navigation elements leading to the previous page.
    back_button = _("Back")
    # Translators: This is a label on delete buttons.
    delete_button = _("Delete")

    delete_confirm_heading = _("Confirm deletion")
    delete_warning = _(
        "Please make sure that this is the item you want to delete. This action cannot be undone!"
    )
    deleted = _("The item has been deleted.")

    saved = _("Your changes have been saved.")
    back_try_again = _("Please go back and try again.")

    # Translators: This is an established term in the context of software development.
    bad_request = _("Bad request.")
    error_sending_mail = _(
        "There was an error sending the mail. Please try again later."
    )
    error_saving_changes = _(
        "We had trouble saving your input – Please see below for details."
    )
    error_permissions_action = _("You do not have permission to perform this action.")

    permission_denied = _("Permission denied.")
    permission_denied_long = (
        _("Sorry, you do not have the required permissions to access this page."),
    )
    not_found = _("Page not found.")
    not_found_long = [
        _("This page does not exist."),
        _("Huh, I could have sworn there was something here."),
        "",
        _("This page is no more."),
        _("This page has ceased to be."),
        _("Huh."),
    ]
    teapot = _("I'm a teapot!")
    teapot_long = [
        _("I'm a little teapot.<br/>Short and stout,"),
        _("Here is my handle<br/>Here is my spout"),
        _("When I get all steamed up,<br/>Hear me shout,"),
        _("Tip me over and pour me out!"),
    ]
    too_early = _("Too early.")
    too_early_long = [
        _("Patience, traveler. The gates haven't opened yet."),
        _("You're early! That's... kind of impressive."),
        _("The future looks great, but it's not quite ready."),
        _("We love your enthusiasm — come back a little later."),
        _("You're ahead of schedule. Coffee, maybe?"),
        _("Not much to see here — yet. Stay tuned!"),
        _("Almost there... but not quite. Hang tight."),
        _("Oops! You're too soon for the party."),
        _("The early bird gets... this error page."),
        _("Wow, someone's eager. Chill — it's not time yet."),
        _("You're early. Like, way too early. Go touch some grass."),
        _("Nice try, keener. Come back when the rest of us are ready."),
        _("Congrats, you broke the space-time continuum."),
        _("This page isn't baked yet. Put it back in the oven."),
        _("The fun starts later. You're just... prematurely curious."),
        _("You must really hate waiting, huh?"),
        _("Did you time travel? Because this definitely isn't live yet."),
        _("Too early. Not even the devs are awake."),
        _("Caught you peeking. Naughty."),
        _("Temporal protocols violated. Please return to your assigned timeline."),
        _("The chickens haven't voted yet. We must wait."),
        _("Loading future... 13%... 13%... 13%... (this might take a while)"),
        _("Our time gnomes are still sharpening their clocks."),
        _("The quantum muffins aren't done rising."),
        _("You've reached the internet's pre-heating phase."),
        _("Reality is buffering. Please insert more ducks."),
        _("We asked the future. It said: 'nope.'"),
        _("This page only exists tomorrow. Sorry, time traveler."),
        _("The secret council of space otters has not yet convened."),
        _("The stars are not aligned for this page yet."),
        _("You've entered the time vortex. Please return to the present."),
        _("The universe is still deciding if this page should exist."),
        _("You've reached the 'before' stage of this page's life."),
        _("This page is still in beta. Like, way in beta."),
        _("The time lords are still debating its existence."),
    ]
    enter_email = _("Email address")
    new_password = _("New password")
    password_repeat = _("New password (again)")
    passwords_differ = _(
        "You entered two different passwords. Please enter the same one twice!"
    )
    password_reset_heading = pgettext_lazy("noun / heading", "Reset password")
    password_reset_question = _("Forgot your password?")
    password_reset_action = _("Let me set a new one!")
    password_reset_nearly_done = _(
        "Now you just need to choose your new password and you are ready to go."
    )
    password_reset_success = _("The password was reset.")

    use_markdown = _("You can use {link_start}Markdown{link_end} here.").format(
        link_start='<a href="https://docs.pretalx.org/user/markdown/" target="_blank" rel="noopener">',
        link_end="</a>",
    )
    public_content = _("This content may be shown publicly.")

    quotation_open = pgettext_lazy("opening quotation mark", "“")
    quotation_close = pgettext_lazy("closing quotation mark", "”")

    # Translators: Used both for language selection for users, and for the language
    # attribute of events and sessions.
    language = _("Language")

    # Translators: Used as settings/section heading
    general = _("General")

    email_subject = pgettext_lazy("email subject", "Subject")
    # Translators: Text is used to describe the main text body of an email, or of
    # similar options like the main text of the CfP or a review. It's separate from
    # the "text" input type used in questions.
    text_body = _("Text")
