import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

patch(ActivityMenu.prototype, {
    async signInOut() {
        this.dropdown.close();
        if (this._attendanceInProgress) {
            return;
        }
        this._attendanceInProgress = true;

        const getCachedCoords = () => {
            try {
                const stored = localStorage.getItem("odoo_attendance_last_geo");
                if (stored) {
                    const parsed = JSON.parse(stored);
                    if (parsed && parsed.latitude && parsed.longitude) {
                        return parsed;
                    }
                }
            } catch (e) {
                console.warn("Failed reading cached geo:", e);
            }
            return null;
        };

        const saveCoords = (latitude, longitude) => {
            try {
                localStorage.setItem("odoo_attendance_last_geo", JSON.stringify({
                    latitude,
                    longitude,
                    timestamp: Date.now()
                }));
            } catch (e) {}
        };

        if (navigator.geolocation && navigator.onLine) {
            navigator.geolocation.getCurrentPosition(
                async ({ coords: { latitude, longitude } }) => {
                    saveCoords(latitude, longitude);
                    await this.checking(latitude, longitude);
                },
                async (err) => {
                    console.warn("Device geolocation unavailable or denied:", err);
                    const cached = getCachedCoords();
                    if (cached) {
                        console.info("Using cached geolocation for check in/out:", cached);
                        await this.checking(cached.latitude, cached.longitude);
                    } else {
                        await this.confirmChecking();
                    }
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 300000,
                }
            );
        } else {
            const cached = getCachedCoords();
            if (cached) {
                await this.checking(cached.latitude, cached.longitude);
            } else {
                await this.checking();
            }
        }
    },
});
