"""
Notifications: the digest a deployment may deliver (docs/design/
decision-lab-phase-3.md, section 4). `digest` builds the message, `schedule`
says when it goes. Pure: core builds every message and sends none; a
deployment's `Notifier` (application/ports.py) delivers it.
"""
