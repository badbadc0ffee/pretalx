from django.dispatch import receiver

from pretalx.common.signals import EventPluginSignal, register_data_exporters


person_details = EventPluginSignal()
"""
This signal is sent when a submission details page is shown in the organiser
view. Receivers can generate HTML fragments containing submission-related
information, such as notes or data from external systems (e.g., issue tracking
systems). These fragments will appear below other rows on the details page.

As with all event-plugin signals, the ``sender`` keyword argument contains the
event. Additionally, the ``submission`` keyword argument includes the submission
instance, and the ``request`` keyword argument contains the request for which
the view is generated.
"""

@receiver(register_data_exporters, dispatch_uid="exporter_builtin_csv_speaker")
def register_speaker_csv_exporter(sender, **kwargs):
    from pretalx.person.exporters import CSVSpeakerExporter

    return CSVSpeakerExporter
