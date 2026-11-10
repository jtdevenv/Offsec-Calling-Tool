import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from dialing import destination, dtmf
from microsip_backend import MicroSipBackend


class PhoneTests(unittest.TestCase):
    def test_destinations_reject_microsip_commands_and_control_characters(self):
        for value in ('/resetnoask', '/exit', '--help', 'sip:a@host\r\nInjected: yes', ''):
            with self.assertRaises(ValueError): destination(value)
        self.assertEqual(destination('+1 (234) 567-8900'), '+12345678900')
        self.assertEqual(destination('sip:100@pbx.example.com'), 'sip:100@pbx.example.com')
        self.assertEqual(destination('*123#', 'pbx.example.com'), 'sip:*123%23@pbx.example.com')

    def test_dtmf_validation(self):
        self.assertEqual(dtmf('12#a'), '12#A')
        for value in ('/exit', '1 2', ''):
            with self.assertRaises(ValueError): dtmf(value)

    def test_bundled_phone_commands_are_literal_argument_lists(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'MicroSIP'/'version'
            folder.mkdir(parents=True)
            exe = folder/'MicroSIP.exe'
            exe.touch()
            phone=MicroSipBackend(temp)
            with patch('microsip_backend.subprocess.Popen') as launch:
                phone.start();phone.dial('+1 234');phone.answer();phone.hangup();phone.send_dtmf('12#');phone.show()
                commands=[c.args[0] for c in launch.call_args_list]
                self.assertEqual([x[1:] for x in commands], [['/minimized'], ['+1234'], ['/answer'], ['/hangupall'], ['/dtmf:12#'], []])
                self.assertTrue(all(x[0]==str(exe.resolve()) for x in commands))
                self.assertTrue(all(c.kwargs['shell'] is False for c in launch.call_args_list))
                before=launch.call_count
                with self.assertRaises(ValueError): phone.dial('/resetnoask')
                self.assertEqual(launch.call_count,before)
