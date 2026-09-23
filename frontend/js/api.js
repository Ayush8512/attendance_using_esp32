const API_BASE_URL = window.location.port === "8000" ? "" : "http://localhost:8000";

async function fetchWithHandler(url, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${url}`, options);
        if (!response.ok) {
            let errorText = await response.text();
            try {
                const parsed = JSON.parse(errorText);
                if (parsed.detail) errorText = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
            } catch (_) {}
            throw new Error(errorText || `API Error: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("API Request Failed:", error);
        throw error;
    }
}

export const api = {
    // Health Check
    healthCheck: () => fetchWithHandler("/health"),

    // Student & Verification
    registerStudent: (formData) => fetchWithHandler("/register", {
        method: "POST",
        body: formData
    }),
    verifyFace: (formData) => fetchWithHandler("/verify", {
        method: "POST",
        body: formData
    }),
    getStudents: (branchCode = '', section = '', q = '') => {
        let query = [];
        if (branchCode) query.push(`branch_code=${encodeURIComponent(branchCode)}`);
        if (section) query.push(`section=${encodeURIComponent(section)}`);
        if (q) query.push(`q=${encodeURIComponent(q)}`);
        const qs = query.length ? `?${query.join('&')}` : '';
        return fetchWithHandler(`/students${qs}`);
    },
    deleteStudent: (rollNo) => fetchWithHandler(`/students/${encodeURIComponent(rollNo)}`, {
        method: "DELETE"
    }),
    unlockStudent: (rollNo) => fetchWithHandler(`/admin/students/${encodeURIComponent(rollNo)}/unlock`, {
        method: "POST"
    }),
    lockStudent: (rollNo) => fetchWithHandler(`/admin/students/${encodeURIComponent(rollNo)}/lock`, {
        method: "POST"
    }),
    getAdminSettings: () => fetchWithHandler("/admin/settings"),
    toggleRegistration: (open) => fetchWithHandler("/admin/settings/registration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ open })
    }),

    // College Master Roster (7 Branches & 4 Years — A1 to G4)
    getRosterBranches: () => fetchWithHandler("/roster/branches"),
    getRosterStudents: (section = '', branchCode = '', year = '', q = '', limit = 200, offset = 0) => {
        let query = [];
        if (section) query.push(`section=${encodeURIComponent(section)}`);
        if (branchCode) query.push(`branch_code=${encodeURIComponent(branchCode)}`);
        if (year) query.push(`year=${encodeURIComponent(year)}`);
        if (q) query.push(`q=${encodeURIComponent(q)}`);
        query.push(`limit=${limit}`);
        query.push(`offset=${offset}`);
        return fetchWithHandler(`/roster/students?${query.join('&')}`);
    },
    lookupRosterStudent: (rollNo) => fetchWithHandler(`/roster/lookup/${encodeURIComponent(rollNo)}`),
    getRosterStats: () => fetchWithHandler("/roster/stats"),

    // Attendance Records
    getAttendance: (rollNo = '', date = '', subject = '', branch = '', section = '') => {
        let query = [];
        if (rollNo) query.push(`roll_no=${encodeURIComponent(rollNo)}`);
        if (date) query.push(`date_filter=${encodeURIComponent(date)}`);
        if (subject) query.push(`subject_filter=${encodeURIComponent(subject)}`);
        if (branch) query.push(`branch_filter=${encodeURIComponent(branch)}`);
        if (section) query.push(`section_filter=${encodeURIComponent(section)}`);
        const qs = query.length ? `?${query.join('&')}` : '';
        return fetchWithHandler(`/attendance${qs}`);
    },

    // Timetable & Strict 10-Min Window Management
    getTimetable: () => fetchWithHandler("/timetable"),
    addTimetableEntry: (formData) => fetchWithHandler("/timetable", {
        method: "POST",
        body: formData
    }),
    deleteTimetableEntry: (id) => fetchWithHandler(`/timetable/${id}`, {
        method: "DELETE"
    }),
    endClass: (formData) => fetchWithHandler("/end_class", {
        method: "POST",
        body: formData
    })
};
