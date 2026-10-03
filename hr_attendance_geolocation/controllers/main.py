# -*- coding: utf-8 -*-
import logging
from odoo import http, _
from odoo.http import request
from odoo.addons.hr_attendance.controllers.main import HrAttendance

_logger = logging.getLogger(__name__)


class HrAttendanceGeolocation(HrAttendance):

    @http.route('/hr_attendance/systray_check_in_out', type="jsonrpc", auth="user")
    def systray_attendance(self, latitude=False, longitude=False):
        employee = request.env.user.with_company(self._get_active_company(request)).employee_id

        # If frontend did not supply coordinates, fallback to employee's or company coordinates
        if not latitude or not longitude or (float(latitude) == 0.0 and float(longitude) == 0.0):
            base_lat, base_lon, base_loc = request.env['hr.attendance']._get_fallback_coordinates(employee.id)
            latitude = base_lat
            longitude = base_lon

        geo_ip_response = self._get_geoip_response(
            mode='systray',
            latitude=latitude,
            longitude=longitude,
            device_tracking_enabled=True  # Force tracking enabled to ensure location capture
        )

        employee._attendance_action_change(geo_ip_response)
        return self._get_employee_info_response(employee)
