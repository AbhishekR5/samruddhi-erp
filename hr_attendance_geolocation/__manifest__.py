# -*- coding: utf-8 -*-
{
    'name': 'Attendance Geolocation & Google Maps Tracker',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Track exact Check-In and Check-Out Google location with 10m variance',
    'description': """
Attendance Geolocation & Google Maps Tracker
============================================
* Captures high-accuracy device geolocation on Check-In and Check-Out.
* Applies an intentional 10-meter geodetic variance from the user's exact coordinates.
* Displays embedded interactive Google Maps preview directly inside Check-In and Check-Out form sections.
* Reverse-geocodes coordinates into human-readable street and city addresses.
* One-click navigation to Google Maps.
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['hr_attendance', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_attendance_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_attendance_geolocation/static/src/components/attendance_menu/attendance_menu.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
