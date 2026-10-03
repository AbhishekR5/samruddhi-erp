# -*- coding: utf-8 -*-
from odoo import models
from .hr_attendance import apply_geodetic_variance, reverse_geocode_coordinates


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _attendance_action_change(self, geo_information=None):
        if not geo_information:
            geo_information = {'mode': 'systray'}

        lat = geo_information.get('latitude')
        lon = geo_information.get('longitude')

        # If coordinates missing or zero, fallback to employee's or company last known location
        if not lat or not lon or (float(lat) == 0.0 and float(lon) == 0.0):
            base_lat, base_lon, base_loc = self.env['hr.attendance']._get_fallback_coordinates(self.id)
            geo_information['latitude'] = base_lat
            geo_information['longitude'] = base_lon
            if not geo_information.get('location') or geo_information.get('location') == 'Unknown':
                geo_information['location'] = base_loc
            lat = base_lat
            lon = base_lon

        if lat and lon:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if lat_f != 0.0 or lon_f != 0.0:
                    # Save exact coordinates
                    geo_information['exact_latitude'] = lat_f
                    geo_information['exact_longitude'] = lon_f

                    # Apply intentional 10-meter geodetic variance
                    varied_lat, varied_lon = apply_geodetic_variance(lat_f, lon_f, 10.0)
                    geo_information['latitude'] = varied_lat
                    geo_information['longitude'] = varied_lon

                    # Resolve human-readable address if location is missing/unknown
                    loc = geo_information.get('location')
                    if not loc or loc == 'Unknown':
                        resolved = reverse_geocode_coordinates(varied_lat, varied_lon)
                        if resolved:
                            geo_information['location'] = resolved
            except (ValueError, TypeError):
                pass

        return super()._attendance_action_change(geo_information=geo_information)
