from pretalx.common.signals import EventPluginSignal

register_mail_placeholders = EventPluginSignal()
"""
This signal is sent out to get all known email text placeholders. Receivers should return
an instance of a subclass of pretalx.mail.placeholder.BaseMailTextPlaceholder or a list of these.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

queuedmail_pre_send = EventPluginSignal()
"""
This signal is sent out before a ``QueuedMail`` will been sent.
Receivers may set the ``sent`` timestamp to skip sending via the regular
email backend but shall not alter any other data of the ``QueuedMail``
instance.

As with all event-plugin signals, the ``sender`` keyword argument will
contain the event. Additionally, the ``mail`` keyword argument contains
the ``QueuedMail`` instance itself.
"""

queuedmail_post_send = EventPluginSignal()
"""
This signal is sent out after a ``QueuedMail`` has been sent. Return value
of receivers will be ignored. Receivers must not alter any data of the
``QueuedMail`` instance.

As with all event-plugin signals, the ``sender`` keyword argument will
contain the event. Additionally, the ``mail`` keyword argument contains
the ``QueuedMail`` instance itself.
"""

mail_form_html = EventPluginSignal()
"""
This signal is sent out to display additional information related to emails in
the internal organiser area.

As with all plugin signals, the ``sender`` keyword argument will contain the
event. Additionally, the signal will be called with the ``request`` it is
processing, and the ``mail`` which is currently displayed.
The receivers are expected to return HTML.
"""

mail_forms = EventPluginSignal()
"""
This signal is sent out to inject additional form fields on the submission
pages in the internal organiser area.

As with all plugin signals, the ``sender`` keyword argument will contain the
event. Additionally, the signal will be called with the ``request`` it is
processing, and the ``mail`` which is currently displayed.
The receivers are expected to return one or more forms.
"""
