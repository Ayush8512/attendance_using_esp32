import { api } from '../api.js';

export default {
    async render(container) {
        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-clock text-highlight"></i>
                        Class Timetable & Strict 10-Min Windows
                    </h2>
                    <p class="text-gray-400 mt-1">
                        Configure daily class start times and strict allowed attendance windows.
                    </p>
                </div>
                <button id="btn-refresh-timetable" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-white rounded-lg border border-gray-600 flex items-center gap-2">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
            </div>

            <!-- Live Active Window Status Card -->
            <div id="live-slot-card" class="bg-cardbg rounded-xl border border-gray-700 p-6 mb-8 shadow-lg">
                <div class="flex items-center justify-center py-6 text-gray-400">
                    <i class="fas fa-spinner fa-spin mr-2"></i> Loading live class status...
                </div>
            </div>

            <!-- Main Content: Form & Table Grid -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <!-- Left: Add New Class Form -->
                <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg h-fit">
                    <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                        <i class="fas fa-plus-circle text-highlight"></i>
                        Add / Update Class
                    </h3>
                    <form id="add-timetable-form" class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-300 mb-1">Day of Week</label>
                            <select id="tt-day" name="day" required class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight">
                                <option value="Monday">Monday</option>
                                <option value="Tuesday">Tuesday</option>
                                <option value="Wednesday">Wednesday</option>
                                <option value="Thursday">Thursday</option>
                                <option value="Friday">Friday</option>
                                <option value="Saturday">Saturday</option>
                                <option value="Sunday">Sunday</option>
                            </select>
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-sm font-medium text-gray-300 mb-1">Start Hour (24h)</label>
                                <input type="number" id="tt-hour" name="hour" min="0" max="23" value="10" required 
                                    class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight" />
                                <span class="text-xs text-gray-500">e.g. 9 for 9 AM, 14 for 2 PM</span>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-300 mb-1">Start Minute</label>
                                <input type="number" id="tt-minute" name="start_minute" min="0" max="59" value="0" required 
                                    class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight" />
                                <span class="text-xs text-gray-500">e.g. 0 or 30</span>
                            </div>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-300 mb-1">
                                Attendance Window (Minutes)
                                <span class="text-xs text-highlight font-semibold ml-1">STRICT</span>
                            </label>
                            <input type="number" id="tt-window" name="allowed_window_minutes" min="1" max="60" value="10" required 
                                class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight" />
                            <span class="text-xs text-gray-400">Late scans after this window will be rejected with 403 error.</span>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-300 mb-1">Subject / Course</label>
                            <input type="text" id="tt-subject" name="subject" placeholder="e.g. Physics, Data Structures" required 
                                class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight" />
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-300 mb-1">Teacher Email</label>
                            <input type="email" id="tt-email" name="teacher_email" placeholder="e.g. prof@college.edu" required 
                                class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight" />
                            <span class="text-xs text-gray-500">Excel report is sent here on class end.</span>
                        </div>

                        <button type="submit" id="btn-save-class" class="w-full py-3 bg-highlight hover:bg-pink-700 text-white font-semibold rounded-lg shadow-md transition-colors flex items-center justify-center gap-2">
                            <i class="fas fa-save"></i> Save Class Schedule
                        </button>
                    </form>
                </div>

                <!-- Right: Full Timetable Table -->
                <div class="lg:col-span-2 bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg">
                    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-2">
                        <h3 class="text-xl font-bold text-white flex items-center gap-2">
                            <i class="fas fa-list-check text-highlight"></i>
                            Scheduled Classes
                        </h3>
                        <div class="flex items-center gap-2">
                            <label class="text-xs text-gray-400">Filter Day:</label>
                            <select id="filter-day" class="px-3 py-1 text-sm rounded bg-darkbg border border-gray-600 text-white">
                                <option value="ALL">All Days</option>
                                <option value="Monday">Monday</option>
                                <option value="Tuesday">Tuesday</option>
                                <option value="Wednesday">Wednesday</option>
                                <option value="Thursday">Thursday</option>
                                <option value="Friday">Friday</option>
                                <option value="Saturday">Saturday</option>
                                <option value="Sunday">Sunday</option>
                            </select>
                        </div>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="border-b border-gray-700 text-gray-400 text-sm">
                                    <th class="py-3 px-4">Day</th>
                                    <th class="py-3 px-4">Time Slot</th>
                                    <th class="py-3 px-4">10-Min Window</th>
                                    <th class="py-3 px-4">Subject</th>
                                    <th class="py-3 px-4">Teacher Email</th>
                                    <th class="py-3 px-4 text-center">Action</th>
                                </tr>
                            </thead>
                            <tbody id="timetable-tbody" class="divide-y divide-gray-700 text-sm">
                                <tr>
                                    <td colspan="6" class="py-8 text-center text-gray-500">Loading schedule...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        let currentData = null;

        const loadTimetable = async () => {
            try {
                const res = await api.getTimetable();
                currentData = res;
                renderLiveCard(res.current_slot);
                renderTable(res.timetable);
            } catch (err) {
                console.error("Failed to load timetable:", err);
                document.getElementById('live-slot-card').innerHTML = `
                    <div class="text-red-400 flex items-center gap-2">
                        <i class="fas fa-exclamation-triangle"></i>
                        Failed to connect to backend: ${err.message}. Make sure backend is running on port 8000.
                    </div>
                `;
            }
        };

        const renderLiveCard = (slot) => {
            const card = document.getElementById('live-slot-card');
            if (!slot || !slot.class) {
                card.innerHTML = `
                    <div class="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div class="flex items-center gap-4">
                            <div class="w-14 h-14 rounded-full bg-gray-700 flex items-center justify-center text-gray-400 text-2xl">
                                <i class="fas fa-moon"></i>
                            </div>
                            <div>
                                <h4 class="text-lg font-bold text-white">No Active Class Session Right Now</h4>
                                <p class="text-sm text-gray-400">Current Server Time: ${slot ? slot.day : ''} ${slot ? slot.time : ''}</p>
                            </div>
                        </div>
                        <span class="px-4 py-1.5 rounded-full bg-gray-700 text-gray-300 text-xs font-semibold">
                            Window Closed
                        </span>
                    </div>
                `;
                return;
            }

            const isWindowOpen = slot.window_status && slot.window_status.is_open;
            card.innerHTML = `
                <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div class="flex items-center gap-4">
                        <div class="w-14 h-14 rounded-full ${isWindowOpen ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'} flex items-center justify-center text-2xl border ${isWindowOpen ? 'border-green-500/40' : 'border-red-500/40'}">
                            <i class="fas ${isWindowOpen ? 'fa-door-open' : 'fa-door-closed'}"></i>
                        </div>
                        <div>
                            <div class="flex items-center gap-3">
                                <h4 class="text-xl font-bold text-white">${slot.class.subject}</h4>
                                <span class="px-3 py-1 rounded-full ${isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'} text-xs font-bold uppercase tracking-wider">
                                    ${isWindowOpen ? '● Attendance Window Open' : '● Window Expired'}
                                </span>
                            </div>
                            <p class="text-sm text-gray-300 mt-1">
                                Teacher: <span class="text-gray-200">${slot.class.teacher_email}</span> | Server Time: <span class="font-mono text-highlight">${slot.time}</span>
                            </p>
                            <p class="text-xs text-gray-400 mt-0.5">
                                ${slot.window_status ? slot.window_status.message : ''}
                            </p>
                        </div>
                    </div>

                    <button id="btn-end-active-class" class="px-5 py-2.5 bg-accent hover:bg-blue-900 text-white text-sm font-semibold rounded-lg border border-blue-500/30 flex items-center gap-2 transition-colors">
                        <i class="fas fa-file-excel text-green-400"></i> End Class & Email Report
                    </button>
                </div>
            `;

            const endBtn = document.getElementById('btn-end-active-class');
            if (endBtn) {
                endBtn.addEventListener('click', async () => {
                    if (!confirm(`Are you sure you want to end class for '${slot.class.subject}' and email the attendance report to ${slot.class.teacher_email}?`)) {
                        return;
                    }
                    endBtn.disabled = true;
                    endBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating & Emailing...';
                    try {
                        const fd = new FormData();
                        fd.append('subject', slot.class.subject);
                        fd.append('teacher_email', slot.class.teacher_email);
                        const res = await api.endClass(fd);
                        
                        if (res.download_url) {
                            const a = document.createElement('a');
                            a.href = res.download_url;
                            a.download = res.filename || `Attendance_${slot.class.subject}.xlsx`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        }

                        showToast(res.message || `Attendance report generated!`, res.email_sent ? "success" : "info");
                    } catch (err) {
                        showToast(`Error: ${err.message}`, "error");
                    } finally {
                        endBtn.disabled = false;
                        endBtn.innerHTML = '<i class="fas fa-file-excel text-green-400"></i> End Class & Email Report';
                    }
                });
            }
        };

        const renderTable = (list) => {
            const tbody = document.getElementById('timetable-tbody');
            const filterDay = document.getElementById('filter-day').value;

            const filtered = (list || []).filter(item => {
                if (filterDay === 'ALL') return true;
                return item.day.toLowerCase() === filterDay.toLowerCase();
            });

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500">No classes found for this filter.</td></tr>`;
                return;
            }

            tbody.innerHTML = filtered.map(item => `
                <tr class="hover:bg-darkbg/50 transition-colors">
                    <td class="py-3 px-4 font-semibold text-white">${item.day}</td>
                    <td class="py-3 px-4 font-mono text-gray-300">${item.time_label}</td>
                    <td class="py-3 px-4">
                        <span class="px-2.5 py-1 rounded-md bg-highlight/20 text-pink-300 border border-highlight/30 text-xs font-medium">
                            ${item.attendance_window}
                        </span>
                    </td>
                    <td class="py-3 px-4 font-medium text-white">${item.subject}</td>
                    <td class="py-3 px-4 text-gray-400 font-mono text-xs">${item.teacher_email}</td>
                    <td class="py-3 px-4 text-center">
                        ${item.id ? `
                            <button data-id="${item.id}" data-subject="${item.subject}" class="btn-delete-class text-red-400 hover:text-red-300 p-1.5 rounded hover:bg-red-500/10">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        ` : `<span class="text-xs text-gray-600">Default</span>`}
                    </td>
                </tr>
            `).join('');

            tbody.querySelectorAll('.btn-delete-class').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.getAttribute('data-id');
                    const subject = btn.getAttribute('data-subject');
                    if (!confirm(`Delete class '${subject}' from timetable?`)) return;

                    try {
                        await api.deleteTimetableEntry(id);
                        await loadTimetable();
                    } catch (err) {
                        alert(`Failed to delete: ${err.message}`);
                    }
                });
            });
        };

        // Event listeners
        document.getElementById('btn-refresh-timetable').addEventListener('click', loadTimetable);
        document.getElementById('filter-day').addEventListener('change', () => {
            if (currentData) renderTable(currentData.timetable);
        });

        // Add class submit
        document.getElementById('add-timetable-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-save-class');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

            try {
                const formData = new FormData(e.target);
                const res = await api.addTimetableEntry(formData);
                alert(res.message);
                e.target.reset();
                document.getElementById('tt-hour').value = '10';
                document.getElementById('tt-minute').value = '0';
                document.getElementById('tt-window').value = '10';
                await loadTimetable();
            } catch (err) {
                alert(`Error saving class: ${err.message}`);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-save"></i> Save Class Schedule';
            }
        });

        // Initial load
        await loadTimetable();
    }
};
