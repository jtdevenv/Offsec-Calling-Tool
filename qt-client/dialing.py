"""Validate destinations before passing them to a phone or SIP library."""
import re


def destination(value, domain=None):
    value = value.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('The destination contains control characters.')
    if value.lower().startswith(('sip:', 'sips:')):
        if not re.fullmatch(r"sips?:[A-Za-z0-9_.!~*'()%+\-]+@[A-Za-z0-9.\-:\[\]]+(?:;transport=(?:udp|tcp|tls))?", value, re.I):
            raise ValueError('Enter a SIP address such as sip:user@example.com.')
        return value
    number = re.sub(r'[ ()\-]', '', value)
    if not re.fullmatch(r'\+?[0-9*#]{1,64}', number):
        raise ValueError('Enter a number or a full sip:user@example.com address.')
    if domain:
        # A # in the SIP user part must be escaped, not treated as a URI fragment.
        return 'sip:' + number.replace('#', '%23') + '@' + domain
    return number


def dtmf(value):
    value = value.strip().upper()
    if not re.fullmatch(r'[0-9A-D*#]{1,64}', value):
        raise ValueError('DTMF accepts 0-9, *, #, and A-D (up to 64 digits).')
    return value
