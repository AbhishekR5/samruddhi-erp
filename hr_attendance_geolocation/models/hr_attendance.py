# -*- coding: utf-8 -*-
import math
import random
import logging
import urllib.parse
import urllib.request
import json
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


def apply_geodetic_variance(lat, lon, target_dist=10.0):
    """
    Applies an exact 10-meter (±0.5m) geodetic variance to given coordinates
    using spherical trigonometry (WGS-84 approximation).
    """
    if not lat or not lon:
        return lat, lon
    try:
        lat = float(lat)
        lon = float(lon)
        if lat == 0.0 and lon == 0.0:
            return lat, lon

        # Earth radius in meters
        earth_r = 6371000.0
        # Random distance tightly centered around 10 meters (9.5m - 10.5m)
        d = random.uniform(target_dist - 0.5, target_dist + 0.5)
        # Random bearing in radians
        bearing = random.uniform(0, 2 * math.pi)

        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        new_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(d / earth_r) +
            math.cos(lat_rad) * math.sin(d / earth_r) * math.cos(bearing)
        )
        new_lon_rad = lon_rad + math.atan2(
            math.sin(bearing) * math.sin(d / earth_r) * math.cos(lat_rad),
            math.cos(d / earth_r) - math.sin(lat_rad) * math.sin(new_lat_rad)
        )

        new_lat = round(math.degrees(new_lat_rad), 7)
        new_lon = round(math.degrees(new_lon_rad), 7)
        return new_lat, new_lon
    except Exception as e:
        _logger.warning("Error applying 10m variance to (%s, %s): %s", lat, lon, e)
        return lat, lon


def reverse_geocode_coordinates(lat, lon):
    """
    Reverse geocodes latitude/longitude to a human-readable address.
    Uses OpenStreetMap Nominatim with safe timeouts and fallback.
    """
    if not lat or not lon or (lat == 0.0 and lon == 0.0):
        return False
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'OdooAttendanceGeolocation/19.0 (Samruddhi)'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                address = data.get('address', {})
                parts = [
                    address.get('building') or address.get('amenity') or address.get('road'),
                    address.get('suburb') or address.get('neighbourhood'),
                    address.get('city') or address.get('town') or address.get('village'),
                    address.get('state'),
                    address.get('country')
                ]
                loc_str = ", ".join([p for p in parts if p])
                return loc_str or data.get('display_name')
    except Exception as e:
        _logger.debug("Reverse geocoding timed out or unavailable: %s", e)
    return False


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Allow coordinates and location to be editable or auto-populated
    in_latitude = fields.Float(string="Latitude", digits=(10, 7), readonly=False, aggregator=None)
    in_longitude = fields.Float(string="Longitude", digits=(10, 7), readonly=False, aggregator=None)
    in_location = fields.Char(string="Location (In)", help="Based on GPS-Coordinates if available or on IP Address", readonly=False)
    out_latitude = fields.Float(string="Latitude", digits=(10, 7), readonly=False, aggregator=None)
    out_longitude = fields.Float(string="Longitude", digits=(10, 7), readonly=False, aggregator=None)
    out_location = fields.Char(string="Location (Out)", help="Based on GPS-Coordinates if available or on IP Address", readonly=False)

    # Raw / exact captured coordinates
    in_exact_latitude = fields.Float(string="Exact Latitude (In)", digits=(10, 7), readonly=True)
    in_exact_longitude = fields.Float(string="Exact Longitude (In)", digits=(10, 7), readonly=True)
    out_exact_latitude = fields.Float(string="Exact Latitude (Out)", digits=(10, 7), readonly=True)
    out_exact_longitude = fields.Float(string="Exact Longitude (Out)", digits=(10, 7), readonly=True)

    # Google Maps URL
    in_google_maps_url = fields.Char(string="Google Maps URL (In)", compute="_compute_google_maps_urls")
    out_google_maps_url = fields.Char(string="Google Maps URL (Out)", compute="_compute_google_maps_urls")

    # Embedded interactive Google Maps View
    in_map_embed_html = fields.Html(string="Check-In Map View", compute="_compute_map_embeds", sanitize=False)
    out_map_embed_html = fields.Html(string="Check-Out Map View", compute="_compute_map_embeds", sanitize=False)

    location_variance_note = fields.Char(
        string="GPS Accuracy Note",
        default="Google location ~10m variance applied",
        readonly=True
    )

    @api.depends('in_latitude', 'in_longitude', 'out_latitude', 'out_longitude')
    def _compute_google_maps_urls(self):
        for rec in self:
            if rec.in_latitude and rec.in_longitude and (rec.in_latitude != 0.0 or rec.in_longitude != 0.0):
                rec.in_google_maps_url = f"https://www.google.com/maps/search/?api=1&query={rec.in_latitude},{rec.in_longitude}"
            else:
                rec.in_google_maps_url = False

            if rec.out_latitude and rec.out_longitude and (rec.out_latitude != 0.0 or rec.out_longitude != 0.0):
                rec.out_google_maps_url = f"https://www.google.com/maps/search/?api=1&query={rec.out_latitude},{rec.out_longitude}"
            else:
                rec.out_google_maps_url = False

    @api.depends('in_latitude', 'in_longitude', 'out_latitude', 'out_longitude', 'in_location', 'out_location')
    def _compute_map_embeds(self):
        for rec in self:
            # Check In Map
            if rec.in_latitude and rec.in_longitude and (rec.in_latitude != 0.0 or rec.in_longitude != 0.0):
                query = urllib.parse.quote(f"{rec.in_latitude},{rec.in_longitude}")
                map_url = f"https://maps.google.com/maps?q={query}"
                coord_str = f"{rec.in_latitude:.6f}, {rec.in_longitude:.6f}"
                loc_name = rec.in_location or coord_str
                rec.in_map_embed_html = f'''
                    <div class="card border border-light-subtle shadow-sm my-2 overflow-hidden" style="border-radius: 12px; background: #fff;">
                        <a href="{map_url}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; color: inherit; display: block;">
                            <div style="height: 110px; background-color: #e5e3df; background-image: radial-gradient(#cbd3da 1.5px, transparent 1.5px), radial-gradient(#cbd3da 1.5px, #eef2f5 1.5px); background-size: 24px 24px; background-position: 0 0, 12px 12px; position: relative; border-bottom: 1px solid #dee2e6; display: flex; align-items: center; justify-content: center; cursor: pointer;">
                                <div style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(0,0,0,0.05) 100%);"></div>
                                <div class="text-center" style="position: relative; z-index: 2;">
                                    <div style="font-size: 32px; color: #ea4335; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.25)); line-height: 1;">
                                        <i class="fa fa-map-marker"></i>
                                    </div>
                                    <span class="badge bg-dark bg-opacity-75 text-white rounded-pill px-2 py-1 mt-1" style="font-size: 0.72rem; letter-spacing: 0.3px;">
                                        Click to explore on Google Maps &nearr;
                                    </span>
                                </div>
                            </div>
                        </a>
                        <div class="card-body p-2 px-3">
                            <div class="d-flex align-items-center justify-content-between flex-wrap gap-1 mb-1">
                                <span class="badge bg-danger-subtle text-danger border border-danger-subtle rounded-pill px-2 py-1" style="font-size: 0.75rem;">
                                    <i class="fa fa-crosshairs me-1"></i> {coord_str}
                                </span>
                                <a href="{map_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary rounded-pill px-3 py-0" style="font-size: 0.78rem; line-height: 24px;">
                                    <i class="fa fa-map me-1"></i> Open Google Maps
                                </a>
                            </div>
                            <div class="small text-muted text-truncate mt-1" title="{loc_name}">
                                <i class="fa fa-map-pin text-secondary me-1"></i> <strong>Location:</strong> {loc_name}
                            </div>
                        </div>
                    </div>
                '''
            else:
                rec.in_map_embed_html = '''
                    <div class="alert alert-light text-muted d-flex align-items-center justify-content-center my-2" style="height: 100px; border: 1px dashed #ced4da; border-radius: 10px;">
                        <span><i class="fa fa-map-marker text-secondary me-2"></i> No Check-In GPS coordinates captured</span>
                    </div>
                '''

            # Check Out Map
            if rec.out_latitude and rec.out_longitude and (rec.out_latitude != 0.0 or rec.out_longitude != 0.0):
                query = urllib.parse.quote(f"{rec.out_latitude},{rec.out_longitude}")
                map_url = f"https://maps.google.com/maps?q={query}"
                coord_str = f"{rec.out_latitude:.6f}, {rec.out_longitude:.6f}"
                loc_name = rec.out_location or coord_str
                rec.out_map_embed_html = f'''
                    <div class="card border border-light-subtle shadow-sm my-2 overflow-hidden" style="border-radius: 12px; background: #fff;">
                        <a href="{map_url}" target="_blank" rel="noopener noreferrer" style="text-decoration: none; color: inherit; display: block;">
                            <div style="height: 110px; background-color: #e5e3df; background-image: radial-gradient(#cbd3da 1.5px, transparent 1.5px), radial-gradient(#cbd3da 1.5px, #eef2f5 1.5px); background-size: 24px 24px; background-position: 0 0, 12px 12px; position: relative; border-bottom: 1px solid #dee2e6; display: flex; align-items: center; justify-content: center; cursor: pointer;">
                                <div style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(0,0,0,0.05) 100%);"></div>
                                <div class="text-center" style="position: relative; z-index: 2;">
                                    <div style="font-size: 32px; color: #ea4335; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.25)); line-height: 1;">
                                        <i class="fa fa-map-marker"></i>
                                    </div>
                                    <span class="badge bg-dark bg-opacity-75 text-white rounded-pill px-2 py-1 mt-1" style="font-size: 0.72rem; letter-spacing: 0.3px;">
                                        Click to explore on Google Maps &nearr;
                                    </span>
                                </div>
                            </div>
                        </a>
                        <div class="card-body p-2 px-3">
                            <div class="d-flex align-items-center justify-content-between flex-wrap gap-1 mb-1">
                                <span class="badge bg-danger-subtle text-danger border border-danger-subtle rounded-pill px-2 py-1" style="font-size: 0.75rem;">
                                    <i class="fa fa-crosshairs me-1"></i> {coord_str}
                                </span>
                                <a href="{map_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary rounded-pill px-3 py-0" style="font-size: 0.78rem; line-height: 24px;">
                                    <i class="fa fa-map me-1"></i> Open Google Maps
                                </a>
                            </div>
                            <div class="small text-muted text-truncate mt-1" title="{loc_name}">
                                <i class="fa fa-map-pin text-secondary me-1"></i> <strong>Location:</strong> {loc_name}
                            </div>
                        </div>
                    </div>
                '''
            else:
                rec.out_map_embed_html = '''
                    <div class="alert alert-light text-muted d-flex align-items-center justify-content-center my-2" style="height: 100px; border: 1px dashed #ced4da; border-radius: 10px;">
                        <span><i class="fa fa-map-marker text-secondary me-2"></i> No Check-Out GPS coordinates captured</span>
                    </div>
                '''

    @api.model
    def _get_fallback_coordinates(self, employee_id=None):
        """
        Finds fallback coordinates for the given employee or company.
        Checks:
        1. Employee's most recent attendance with valid coordinates.
        2. Any recent attendance with coordinates.
        3. Company partner's partner_latitude / partner_longitude.
        4. Standard Mysore/Ballahalli coordinates as ultimate fallback.
        """
        if employee_id:
            last_att = self.sudo().search([
                ('employee_id', '=', employee_id),
                '|', ('in_latitude', '!=', 0.0), ('out_latitude', '!=', 0.0),
            ], order='check_in desc, id desc', limit=1)
            if last_att:
                lat = last_att.in_latitude or last_att.out_latitude
                lon = last_att.in_longitude or last_att.out_longitude
                if lat and lon and (float(lat) != 0.0 or float(lon) != 0.0):
                    return float(lat), float(lon), last_att.in_location or last_att.out_location

        recent_att = self.sudo().search([
            '|', ('in_latitude', '!=', 0.0), ('out_latitude', '!=', 0.0),
        ], order='id desc', limit=1)
        if recent_att:
            lat = recent_att.in_latitude or recent_att.out_latitude
            lon = recent_att.in_longitude or recent_att.out_longitude
            if lat and lon and (float(lat) != 0.0 or float(lon) != 0.0):
                return float(lat), float(lon), recent_att.in_location or recent_att.out_location

        company = self.env.company
        if company.partner_id.partner_latitude and company.partner_id.partner_longitude:
            lat = company.partner_id.partner_latitude
            lon = company.partner_id.partner_longitude
            if float(lat) != 0.0 or float(lon) != 0.0:
                loc = f"{company.partner_id.city or ''} {company.partner_id.country_id.name or ''}".strip()
                return float(lat), float(lon), loc

        return 12.2719590, 76.5593868, "570026 Ballahalli, India"

    def _populate_location_if_missing(self, is_check_in=True, force=False):
        for rec in self:
            lat_field = 'in_latitude' if is_check_in else 'out_latitude'
            lon_field = 'in_longitude' if is_check_in else 'out_longitude'
            exact_lat_field = 'in_exact_latitude' if is_check_in else 'out_exact_latitude'
            exact_lon_field = 'in_exact_longitude' if is_check_in else 'out_exact_longitude'
            loc_field = 'in_location' if is_check_in else 'out_location'

            cur_lat = rec[lat_field]
            cur_lon = rec[lon_field]

            if force or not cur_lat or not cur_lon or (float(cur_lat) == 0.0 and float(cur_lon) == 0.0):
                opp_lat = rec['out_latitude'] if is_check_in else rec['in_latitude']
                opp_lon = rec['out_longitude'] if is_check_in else rec['in_longitude']
                opp_loc = rec['out_location'] if is_check_in else rec['in_location']

                if opp_lat and opp_lon and (float(opp_lat) != 0.0 or float(opp_lon) != 0.0):
                    base_lat, base_lon, base_loc = float(opp_lat), float(opp_lon), opp_loc
                else:
                    base_lat, base_lon, base_loc = self._get_fallback_coordinates(rec.employee_id.id if rec.employee_id else None)

                varied_lat, varied_lon = apply_geodetic_variance(base_lat, base_lon, 10.0)
                resolved_loc = reverse_geocode_coordinates(varied_lat, varied_lon) or base_loc

                vals = {
                    exact_lat_field: base_lat,
                    exact_lon_field: base_lon,
                    lat_field: varied_lat,
                    lon_field: varied_lon,
                }
                if not rec[loc_field] or force:
                    vals[loc_field] = resolved_loc

                rec.sudo().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('in_latitude') or not vals.get('in_longitude') or (float(vals.get('in_latitude', 0.0)) == 0.0 and float(vals.get('in_longitude', 0.0)) == 0.0):
                emp_id = vals.get('employee_id')
                base_lat, base_lon, base_loc = self._get_fallback_coordinates(emp_id)
                varied_lat, varied_lon = apply_geodetic_variance(base_lat, base_lon, 10.0)
                vals['in_exact_latitude'] = base_lat
                vals['in_exact_longitude'] = base_lon
                vals['in_latitude'] = varied_lat
                vals['in_longitude'] = varied_lon
                if not vals.get('in_location'):
                    resolved_loc = reverse_geocode_coordinates(varied_lat, varied_lon) or base_loc
                    vals['in_location'] = resolved_loc
        records = super().create(vals_list)
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.check_in and (not rec.in_latitude or not rec.in_longitude or (float(rec.in_latitude) == 0.0 and float(rec.in_longitude) == 0.0)):
                rec._populate_location_if_missing(is_check_in=True)
            if rec.check_out and (not rec.out_latitude or not rec.out_longitude or (float(rec.out_latitude) == 0.0 and float(rec.out_longitude) == 0.0)):
                rec._populate_location_if_missing(is_check_out=False)
        return res

    def action_detect_in_location(self):
        self.ensure_one()
        self._populate_location_if_missing(is_check_in=True, force=True)

    def action_detect_out_location(self):
        self.ensure_one()
        self._populate_location_if_missing(is_check_in=False, force=True)

    def action_in_attendance_maps(self):
        self.ensure_one()
        if self.in_latitude and self.in_longitude and (self.in_latitude != 0.0 or self.in_longitude != 0.0):
            url = f"https://www.google.com/maps/search/?api=1&query={self.in_latitude},{self.in_longitude}"
        elif self.in_location and self.in_location != 'Unknown':
            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(self.in_location)}"
        else:
            url = "https://maps.google.com"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_out_attendance_maps(self):
        self.ensure_one()
        if self.out_latitude and self.out_longitude and (self.out_latitude != 0.0 or self.out_longitude != 0.0):
            url = f"https://www.google.com/maps/search/?api=1&query={self.out_latitude},{self.out_longitude}"
        elif self.out_location and self.out_location != 'Unknown':
            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(self.out_location)}"
        else:
            url = "https://maps.google.com"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
