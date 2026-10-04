import { api } from '../api.js';
import { showToast } from '../components/toast.js';

const BRANCH_MAP = {
    'A': 'Computer Science & Engineering (CSE)',
    'B': 'Electronics Engineering (ECE)',
    'C': 'Industrial & Production Engineering (IPE)',
    'D': 'Mechanical Engineering (ME)',
    'E': 'Instrumentation & Control Engineering (ICE)',
    'F': 'Electrical Engineering (EE)',
    'G': 'Civil Engineering (CE)',
};

const YEAR_MAP = {
    1: '1st Year',
    2: '2nd Year',
    3: '3rd Year',
    4: '4th Year',
};

export default {
    async render(container) {
        // Detect current user role
        let currentUser = null;
        try {
            const rawUser = localStorage.getItem('currentUser');
            if (rawUser) currentUser = JSON.parse(rawUser);
        } catch (_) {}

        const isTeacherOrAdmin = currentUser && (currentUser.role === 'admin' || currentUser.role === 'teacher');

        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-clock text-highlight"></i>
                        Weekly Timetable & Live Alerts
                    </h2>
                    <p class="text-gray-400 mt-1">
                        Lecture slot tracking, strict 10-minute attendance window countdowns, and active classroom notifications.
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    ${isTeacherOrAdmin ? `
                        <button id="btn-bulk-upload-timetable" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg border border-blue-500 flex items-center gap-2 text-sm font-semibold shadow-sm transition-colors">
                            <i class="fas fa-file-upload"></i> Upload PDF / Excel / CSV
                        </button>
                    ` : ''}
                    <button id="btn-refresh-timetable" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-white rounded-lg border border-gray-600 flex items-center gap-2 text-sm font-semibold transition-colors">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                </div>
            </div>

            <!-- Live Active Window & Countdown Status Card -->
            <div id="live-slot-card" class="bg-cardbg rounded-lg border border-gray-700 p-6 mb-8 shadow-sm relative overflow-hidden">
                <div class="flex items-center justify-center py-6 text-gray-400">
                    <i class="fas fa-spinner fa-spin mr-2"></i> Syncing live timetable slot and active countdown...
                </div>
            </div>

            <!-- Main Content Grid -->
            <div class="grid grid-cols-1 ${isTeacherOrAdmin ? 'lg:grid-cols-3' : 'grid-cols-1'} gap-8">
                ${isTeacherOrAdmin ? `
                    <!-- Left: Schedule Class Form (Teachers/Admin Only) -->
                    <div class="bg-cardbg rounded-lg border border-gray-700 p-6 shadow-sm h-fit">
                        <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <i class="fas fa-calendar-plus text-highlight"></i>
                            Schedule Class Slot
                        </h3>
                        <form id="add-timetable-form" class="space-y-4">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Day of Week *</label>
                                <select id="tt-day" name="day" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                                    <option value="Monday">Monday</option>
                                    <option value="Tuesday">Tuesday</option>
                                    <option value="Wednesday">Wednesday</option>
                                    <option value="Thursday">Thursday</option>
                                    <option value="Friday">Friday</option>
                                    <option value="Saturday">Saturday</option>
                                    <option value="Sunday">Sunday</option>
                                </select>
                            </div>

                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs font-medium text-gray-300 mb-1">Branch (A–G)</label>
                                    <select id="tt-branch" name="branch_code" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                                        <option value="">General / All</option>
                                        <option value="A">A - Computer Science (CSE)</option>
                                        <option value="B">B - Electronics (ECE)</option>
                                        <option value="C">C - Industrial (IPE)</option>
                                        <option value="D">D - Mechanical (ME)</option>
                                        <option value="E">E - Instrumentation (ICE)</option>
                                        <option value="F">F - Electrical (EE)</option>
                                        <option value="G">G - Civil (CE)</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-xs font-medium text-gray-300 mb-1">Academic Year</label>
                                    <select id="tt-year" name="year" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                                        <option value="0">All Years</option>
                                        <option value="1">1st Year</option>
                                        <option value="2">2nd Year</option>
                                        <option value="3">3rd Year</option>
                                        <option value="4">4th Year</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Section (e.g. A1, B2)</label>
                                <select id="tt-section" name="section" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                                    <option value="">Auto / All Sections</option>
                                </select>
                            </div>

                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs font-medium text-gray-300 mb-1">Start Time *</label>
                                    <input type="time" id="tt-start-time" name="start_time" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                                </div>
                                <div>
                                    <label class="block text-xs font-medium text-gray-300 mb-1">End Time *</label>
                                    <input type="time" id="tt-end-time" name="end_time" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                                </div>
                            </div>

                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">
                                    Attendance Window (Minutes)
                                    <span class="text-[10px] text-highlight font-semibold ml-1">STRICT 10 MIN</span>
                                </label>
                                <input type="number" id="tt-window" name="allowed_window_minutes" min="1" max="60" value="10" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            </div>

                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Subject / Course Name *</label>
                                <input type="text" id="tt-subject" name="subject" placeholder="e.g. Data Structures, Physics" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            </div>

                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Teacher Email *</label>
                                <input type="email" id="tt-email" name="teacher_email" value="${currentUser ? currentUser.email : ''}" placeholder="e.g. prof@iert.ac.in" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            </div>

                            <button type="submit" id="btn-save-class" class="w-full py-2.5 bg-highlight hover:bg-blue-700 text-white font-semibold rounded-md shadow-sm transition-colors flex items-center justify-center gap-2 text-sm">
                                <i class="fas fa-save"></i> Save Class Schedule
                            </button>
                        </form>
                    </div>
                ` : ''}

                <!-- Timetable Schedule View -->
                <div class="${isTeacherOrAdmin ? 'lg:col-span-2' : 'col-span-1'} bg-cardbg rounded-lg border border-gray-700 p-6 shadow-sm">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-3">
                        <h3 class="text-xl font-bold text-white flex items-center gap-2">
                            <i class="fas fa-list-check text-highlight"></i>
                            Weekly Class Schedule
                        </h3>
                        <div class="flex flex-wrap items-center gap-2">
                            <select id="filter-branch" class="px-2.5 py-1 text-xs rounded bg-darkbg border border-gray-600 text-white">
                                <option value="ALL">All Branches</option>
                                <option value="A">Branch A (CSE)</option>
                                <option value="B">Branch B (ECE)</option>
                                <option value="C">Branch C (IPE)</option>
                                <option value="D">Branch D (ME)</option>
                                <option value="E">Branch E (ICE)</option>
                                <option value="F">Branch F (EE)</option>
                                <option value="G">Branch G (CE)</option>
                            </select>
                            <select id="filter-year" class="px-2.5 py-1 text-xs rounded bg-darkbg border border-gray-600 text-white">
                                <option value="ALL">All Years</option>
                                <option value="1">1st Year</option>
                                <option value="2">2nd Year</option>
                                <option value="3">3rd Year</option>
                                <option value="4">4th Year</option>
                            </select>
                            <select id="filter-day" class="px-2.5 py-1 text-xs rounded bg-darkbg border border-gray-600 text-white">
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
                                <tr class="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider">
                                    <th class="py-3 px-3">Day & Time</th>
                                    <th class="py-3 px-3">Branch & Year</th>
                                    <th class="py-3 px-3">Section</th>
                                    <th class="py-3 px-3">Window</th>
                                    <th class="py-3 px-3">Subject</th>
                                    <th class="py-3 px-3">Teacher Email</th>
                                    ${isTeacherOrAdmin ? `<th class="py-3 px-3 text-center">Actions</th>` : ''}
                                </tr>
                            </thead>
                            <tbody id="timetable-tbody" class="divide-y divide-gray-700 text-xs">
                                <tr>
                                    <td colspan="${isTeacherOrAdmin ? '7' : '6'}" class="py-8 text-center text-gray-500">Loading schedule...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        let currentData = null;
        let countdownTimer = null;

        // Dynamic Section options generator
        if (isTeacherOrAdmin) {
            const updateFormSections = () => {
                const branch = document.getElementById('tt-branch').value;
                const year = parseInt(document.getElementById('tt-year').value || '0');
                const sectionSelect = document.getElementById('tt-section');
                if (!sectionSelect) return;
                const currentVal = sectionSelect.value;
                
                sectionSelect.innerHTML = '<option value="">Auto / All Sections</option>';
                const branches = branch ? [branch] : ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
                const years = (year > 0) ? [year] : [1, 2, 3, 4];

                branches.forEach(b => {
                    years.forEach(y => {
                        const sec = `${b}${y}`;
                        const opt = document.createElement('option');
                        opt.value = sec;
                        opt.textContent = `Section ${sec} (${YEAR_MAP[y]} • ${b})`;
                        if (sec === currentVal) opt.selected = true;
                        sectionSelect.appendChild(opt);
                    });
                });
            };

            document.getElementById('tt-branch')?.addEventListener('change', updateFormSections);
            document.getElementById('tt-year')?.addEventListener('change', updateFormSections);
            updateFormSections();
        }

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
                        Failed to connect to backend: ${err.message}.
                    </div>
                `;
            }
        };

        const renderLiveCard = (slot) => {
            const card = document.getElementById('live-slot-card');
            if (countdownTimer) clearInterval(countdownTimer);

            if (!slot || !slot.class) {
                card.innerHTML = `
                    <div class="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-md bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-400 text-xl">
                                <i class="fas fa-moon"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-white">No Active Lecture Slot Right Now</h4>
                                <p class="text-xs text-gray-400">Current Server Time: <span class="font-mono text-gray-300">${slot ? slot.day : ''} ${slot ? slot.time : ''}</span></p>
                            </div>
                        </div>
                        <span class="px-3 py-1 rounded-md bg-gray-800 border border-gray-700 text-gray-400 text-xs font-semibold">
                            Window Closed
                        </span>
                    </div>
                `;
                return;
            }

            const isWindowOpen = slot.window_status && slot.window_status.is_open;
            const branchCode = slot.class.branch_code || '';
            const branchName = slot.class.branch_name || BRANCH_MAP[branchCode] || branchCode;
            const section = slot.class.section || '';
            const yearNum = slot.class.year || (section.length >= 2 && !isNaN(section[1]) ? parseInt(section[1]) : 0);
            const yearLabel = YEAR_MAP[yearNum] || (yearNum > 0 ? `${yearNum}th Year` : 'General');

            card.innerHTML = `
                <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div class="flex items-center gap-4">
                        <div class="w-14 h-14 rounded-xl ${isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40 animate-pulse' : 'bg-red-500/20 text-red-400 border border-red-500/40'} flex items-center justify-center text-2xl shrink-0">
                            <i class="fas ${isWindowOpen ? 'fa-clock' : 'fa-lock'}"></i>
                        </div>
                        <div>
                            <div class="flex flex-wrap items-center gap-2">
                                <h4 class="text-xl font-bold text-white">${slot.class.subject}</h4>
                                <span class="px-2.5 py-0.5 rounded-md ${isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'} text-xs font-bold uppercase tracking-wider">
                                    ${isWindowOpen ? '● LIVE Attendance Window Open' : '● Window Expired'}
                                </span>
                                ${yearNum ? `<span class="px-2 py-0.5 rounded bg-slate-700 text-slate-200 border border-slate-600 text-xs font-semibold">${yearLabel}</span>` : ''}
                                ${section ? `<span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-mono font-semibold">Sec ${section}</span>` : ''}
                            </div>
                            <p class="text-xs text-gray-300 mt-1">
                                Faculty: <span class="text-gray-200 font-semibold">${slot.class.teacher_email}</span> | Server Time: <span class="font-mono text-highlight">${slot.time}</span>
                            </p>
                            <div id="window-countdown-ticker" class="mt-2 text-xs font-mono text-amber-300 flex items-center gap-1.5">
                                <i class="fas fa-hourglass-half"></i> <span>Calculating window countdown...</span>
                            </div>
                        </div>
                    </div>

                    ${isTeacherOrAdmin ? `
                        <button id="btn-end-active-class" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-md border border-slate-600 flex items-center gap-2 transition-colors shadow-sm shrink-0">
                            <i class="fas fa-file-excel text-green-400"></i> End Class & Email Sheet
                        </button>
                    ` : ''}
                </div>
            `;

            // Live 1-Second Ticker Countdown
            if (isWindowOpen && slot.window_status && slot.window_status.window_end) {
                const tickerEl = document.getElementById('window-countdown-ticker');
                const windowEndStr = slot.window_status.window_end;
                const [targetH, targetM] = windowEndStr.split(':').map(Number);
                
                const updateTicker = () => {
                    const now = new Date();
                    const target = new Date();
                    target.setHours(targetH, targetM, 0, 0);

                    const diffMs = target - now;
                    if (diffMs <= 0) {
                        if (tickerEl) tickerEl.innerHTML = `<span class="text-red-400 font-bold">⛔ 10-Minute Attendance Window Expired!</span>`;
                        clearInterval(countdownTimer);
                        return;
                    }

                    const mins = Math.floor(diffMs / 60000);
                    const secs = Math.floor((diffMs % 60000) / 1000);
                    if (tickerEl) {
                        tickerEl.innerHTML = `
                            <span class="bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-1 rounded font-bold">
                                ⏱️ Countdown: ${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')} remaining in strict window
                            </span>
                        `;
                    }
                };

                updateTicker();
                countdownTimer = setInterval(updateTicker, 1000);
            }

            const endBtn = document.getElementById('btn-end-active-class');
            if (endBtn) {
                endBtn.addEventListener('click', async () => {
                    if (!confirm(`End class for '${slot.class.subject}' and email attendance sheet to ${slot.class.teacher_email}?`)) return;
                    endBtn.disabled = true;
                    endBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                    try {
                        const fd = new FormData();
                        fd.append('subject', slot.class.subject);
                        fd.append('teacher_email', slot.class.teacher_email);
                        if (section) fd.append('section', section);
                        if (branchCode) fd.append('branch', branchCode);
                        if (yearNum) fd.append('year', yearNum);

                        const res = await api.endClass(fd);
                        if (res.download_url) {
                            const a = document.createElement('a');
                            a.href = res.download_url;
                            a.download = res.filename || `Attendance_${slot.class.subject}.xlsx`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        }
                        showToast(res.message || `Attendance report generated!`, "success");
                    } catch (err) {
                        showToast(`Error: ${err.message}`, "error");
                    } finally {
                        endBtn.disabled = false;
                        endBtn.innerHTML = '<i class="fas fa-file-excel text-green-400"></i> End Class & Email Sheet';
                    }
                });
            }
        };

        const renderTable = (list) => {
            const tbody = document.getElementById('timetable-tbody');
            const filterDay = document.getElementById('filter-day').value;
            const filterBranch = document.getElementById('filter-branch').value;
            const filterYear = document.getElementById('filter-year').value;

            const filtered = (list || []).filter(item => {
                if (filterDay !== 'ALL' && item.day.toLowerCase() !== filterDay.toLowerCase()) return false;
                if (filterBranch !== 'ALL' && (item.branch_code || '').toUpperCase() !== filterBranch.toUpperCase()) return false;
                if (filterYear !== 'ALL' && String(item.year || 0) !== String(filterYear)) return false;
                return true;
            });

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="${isTeacherOrAdmin ? '7' : '6'}" class="py-8 text-center text-gray-500">No classes found for this filter.</td></tr>`;
                return;
            }

            tbody.innerHTML = filtered.map(item => {
                const bCode = item.branch_code || '';
                const bName = item.branch_name || BRANCH_MAP[bCode] || '';
                const yrNum = item.year || 0;
                const yrLabel = item.year_label || YEAR_MAP[yrNum] || (yrNum ? `${yrNum}th Year` : 'All Years');
                const sec = item.section || 'All';

                return `
                    <tr class="hover:bg-darkbg/50 transition-colors">
                        <td class="py-3 px-3">
                            <div class="font-semibold text-white">${item.day}</div>
                            <div class="font-mono text-gray-400 text-[11px]">${item.time_label}</div>
                        </td>
                        <td class="py-3 px-3">
                            ${bCode ? `
                                <div class="font-semibold text-yellow-300 text-xs">Branch ${bCode}</div>
                                <div class="text-[10px] text-gray-400 truncate max-w-[140px]">${bName}</div>
                            ` : `<span class="text-gray-500">General</span>`}
                            <span class="inline-block mt-0.5 px-1.5 py-0.5 rounded bg-slate-700 text-slate-200 border border-slate-600 text-[10px] font-semibold">${yrLabel}</span>
                        </td>
                        <td class="py-3 px-3">
                            ${sec && sec !== 'All Sections' && sec !== 'All' ? `
                                <span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-mono font-bold">${sec}</span>
                            ` : `<span class="text-gray-500 text-xs">All</span>`}
                        </td>
                        <td class="py-3 px-3">
                            <span class="px-2 py-0.5 rounded-md bg-blue-900/30 text-blue-300 border border-blue-800/50 text-[11px] font-medium whitespace-nowrap">
                                ${item.attendance_window}
                            </span>
                        </td>
                        <td class="py-3 px-3">
                            <span class="font-medium text-white">${item.subject}</span>
                        </td>
                        <td class="py-3 px-3 text-gray-400 font-mono text-[11px]">${item.teacher_email}</td>
                        ${isTeacherOrAdmin ? `
                            <td class="py-3 px-3 text-center">
                                <div class="flex items-center justify-center gap-1">
                                    <button data-subject="${item.subject}" data-email="${item.teacher_email}" data-branch="${bCode}" data-year="${yrNum}" data-section="${sec}" class="btn-generate-class-sheet text-green-400 hover:text-green-300 p-1.5 rounded hover:bg-green-500/10" title="Generate Excel Attendance Report">
                                        <i class="fas fa-file-excel"></i>
                                    </button>
                                    ${item.id ? `
                                        <button data-id="${item.id}" data-subject="${item.subject}" class="btn-delete-class text-red-400 hover:text-red-300 p-1.5 rounded hover:bg-red-500/10" title="Delete Schedule">
                                            <i class="fas fa-trash-alt"></i>
                                        </button>
                                    ` : `<span class="text-[10px] text-gray-600">Default</span>`}
                                </div>
                            </td>
                        ` : ''}
                    </tr>
                `;
            }).join('');

            if (isTeacherOrAdmin) {
                tbody.querySelectorAll('.btn-delete-class').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const id = btn.getAttribute('data-id');
                        const subject = btn.getAttribute('data-subject');
                        if (!confirm(`Delete class '${subject}' from timetable?`)) return;
                        try {
                            await api.deleteTimetableEntry(id);
                            showToast(`Deleted '${subject}' from schedule`, "success");
                            await loadTimetable();
                        } catch (err) {
                            showToast(`Failed to delete: ${err.message}`, "error");
                        }
                    });
                });
            }
        };

        // Render Bulk Upload Modal if Teacher or Admin
        if (isTeacherOrAdmin) {
            const modalDiv = document.createElement('div');
            modalDiv.id = 'bulk-timetable-modal';
            modalDiv.className = 'fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden';
            modalDiv.innerHTML = `
                <div class="bg-cardbg border border-gray-700 rounded-xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[90vh] flex flex-col">
                    <div class="flex items-center justify-between border-b border-gray-700 pb-4 mb-3 shrink-0">
                        <h3 class="text-lg font-bold text-white flex items-center gap-2">
                            <i class="fas fa-cloud-upload-alt text-blue-500"></i> Bulk Weekly Schedule & PDF Timetable Uploader
                        </h3>
                        <button id="close-bulk-modal-btn" class="text-gray-400 hover:text-white">
                            <i class="fas fa-times text-lg"></i>
                        </button>
                    </div>

                    <!-- Upload Method Tabs -->
                    <div class="flex border-b border-gray-700 mb-4 gap-2 text-xs font-semibold shrink-0">
                        <button id="tab-btn-file" class="px-3 py-2 border-b-2 border-blue-500 text-blue-400">
                            📁 Upload File (Excel / CSV / PDF)
                        </button>
                        <button id="tab-btn-manual" class="px-3 py-2 border-b-2 border-transparent text-gray-400 hover:text-white">
                            ✏️ Manual Batch Grid Builder
                        </button>
                    </div>

                    <!-- Tab 1: File Upload (Excel, CSV, PDF) -->
                    <div id="tab-file-upload-content" class="flex-1 overflow-y-auto space-y-4">
                        <div class="border-2 border-dashed border-gray-600 hover:border-blue-500 rounded-xl p-6 text-center transition-colors bg-darkbg/40 cursor-pointer" id="drop-zone">
                            <i class="fas fa-file-pdf text-red-400 text-3xl mb-2"></i>
                            <i class="fas fa-file-excel text-green-400 text-3xl mb-2 ml-2"></i>
                            <i class="fas fa-file-csv text-blue-400 text-3xl mb-2 ml-2"></i>
                            <h4 class="text-sm font-bold text-white">Drag & Drop your Timetable File here</h4>
                            <p class="text-xs text-gray-400 mt-1">Supports <code class="text-red-300">.pdf</code>, <code class="text-green-300">.xlsx</code>, <code class="text-green-300">.xls</code>, and <code class="text-blue-300">.csv</code> files</p>
                            <input type="file" id="timetable-file-input" accept=".pdf,.xlsx,.xls,.csv" class="hidden" />
                            <button type="button" id="btn-browse-file" class="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold">
                                Browse Files
                            </button>
                        </div>

                        <div id="file-selected-info" class="hidden bg-darkbg border border-gray-700 rounded-lg p-3 text-xs flex items-center justify-between">
                            <span id="selected-filename-text" class="font-mono text-blue-300"></span>
                            <button type="button" id="btn-submit-file-upload" class="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded font-bold text-xs">
                                Upload & Detect Schedule
                            </button>
                        </div>

                        <div class="bg-blue-950/40 border border-blue-800/50 rounded-lg p-3 text-xs text-blue-200 space-y-1">
                            <div class="font-bold flex items-center justify-between">
                                <span>💡 Need a reference template?</span>
                                <a href="/timetable/sample-template" target="_blank" download class="underline text-blue-300 hover:text-white font-mono text-[11px]">Download Sample CSV</a>
                            </div>
                            <p class="text-[11px] text-gray-400">PDF uploader automatically parses days of week, timing slots, teacher email addresses, and section codes (e.g. A1, B2).</p>
                        </div>
                    </div>

                    <!-- Tab 2: Manual Grid Builder -->
                    <div id="tab-manual-content" class="hidden flex-1 overflow-y-auto space-y-4">
                        <form id="bulk-timetable-form" class="space-y-4">
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div>
                                    <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Teacher Email *</label>
                                    <input type="email" id="bulk-teacher-email" value="${currentUser ? currentUser.email : ''}" required class="w-full bg-darkbg border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200">
                                </div>
                                <div>
                                    <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Target Section *</label>
                                    <input type="text" id="bulk-section" required placeholder="e.g. A1, B2" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200">
                                </div>
                            </div>

                            <div class="border-t border-gray-700 pt-3">
                                <div class="flex items-center justify-between mb-2">
                                    <label class="text-xs font-semibold text-gray-300 uppercase">Weekly Class Slots</label>
                                    <button type="button" id="add-bulk-row-btn" class="text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 border border-gray-600 px-2.5 py-1 rounded flex items-center gap-1">
                                        <i class="fas fa-plus"></i> Add Class Row
                                    </button>
                                </div>
                                <div id="bulk-rows-container" class="space-y-2"></div>
                            </div>

                            <div class="pt-2 border-t border-gray-700 flex justify-end gap-3">
                                <button type="button" id="cancel-bulk-modal-btn" class="px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
                                <button type="submit" id="btn-submit-bulk-timetable" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2 rounded-lg text-sm">
                                    Upload Full Schedule
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;
            document.body.appendChild(modalDiv);

            // Tab toggling inside modal
            const tabBtnFile = document.getElementById('tab-btn-file');
            const tabBtnManual = document.getElementById('tab-btn-manual');
            const fileContent = document.getElementById('tab-file-upload-content');
            const manualContent = document.getElementById('tab-manual-content');

            tabBtnFile?.addEventListener('click', () => {
                fileContent.classList.remove('hidden');
                manualContent.classList.add('hidden');
                tabBtnFile.className = 'px-3 py-2 border-b-2 border-blue-500 text-blue-400';
                tabBtnManual.className = 'px-3 py-2 border-b-2 border-transparent text-gray-400 hover:text-white';
            });

            tabBtnManual?.addEventListener('click', () => {
                fileContent.classList.add('hidden');
                manualContent.classList.remove('hidden');
                tabBtnManual.className = 'px-3 py-2 border-b-2 border-blue-500 text-blue-400';
                tabBtnFile.className = 'px-3 py-2 border-b-2 border-transparent text-gray-400 hover:text-white';
            });

            // File selection & Drag-and-drop
            const fileInput = document.getElementById('timetable-file-input');
            const browseBtn = document.getElementById('btn-browse-file');
            const dropZone = document.getElementById('drop-zone');
            const fileInfo = document.getElementById('file-selected-info');
            const filenameText = document.getElementById('selected-filename-text');
            const submitFileBtn = document.getElementById('btn-submit-file-upload');

            browseBtn?.addEventListener('click', () => fileInput.click());
            dropZone?.addEventListener('click', (e) => {
                if (e.target !== browseBtn) fileInput.click();
            });

            fileInput?.addEventListener('change', () => {
                if (fileInput.files && fileInput.files[0]) {
                    filenameText.textContent = `📄 Selected File: ${fileInput.files[0].name} (${(fileInput.files[0].size / 1024).toFixed(1)} KB)`;
                    fileInfo.classList.remove('hidden');
                }
            });

            submitFileBtn?.addEventListener('click', async () => {
                if (!fileInput.files || !fileInput.files[0]) {
                    showToast("Please select a CSV, Excel, or PDF file.", "error");
                    return;
                }
                submitFileBtn.disabled = true;
                submitFileBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Parsing Timetable...';

                try {
                    const fd = new FormData();
                    fd.append('file', fileInput.files[0]);
                    const res = await api.uploadTimetableFile(fd);
                    showToast(res.message || `Successfully processed timetable file!`, "success");
                    document.getElementById('bulk-timetable-modal').classList.add('hidden');
                    fileInput.value = '';
                    fileInfo.classList.add('hidden');
                    await loadTimetable();
                } catch (err) {
                    showToast(`File upload error: ${err.message}`, "error");
                } finally {
                    submitFileBtn.disabled = false;
                    submitFileBtn.textContent = 'Upload & Detect Schedule';
                }
            });

            // Dynamic Rows Helper for Manual Builder
            const rowsContainer = document.getElementById('bulk-rows-container');
            function addBulkRow(day = "Monday", hour = 9, subject = "Mathematics", windowMins = 10) {
                const rowId = 'row-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4);
                const rowDiv = document.createElement('div');
                rowDiv.id = rowId;
                rowDiv.className = 'grid grid-cols-12 gap-2 items-center bg-darkbg/60 p-2 rounded-lg border border-gray-700/60 text-xs';
                rowDiv.innerHTML = `
                    <div class="col-span-3">
                        <select class="bulk-row-day w-full bg-darkbg border border-gray-700 text-white rounded px-2 py-1 text-xs">
                            <option value="Monday" ${day === 'Monday' ? 'selected' : ''}>Monday</option>
                            <option value="Tuesday" ${day === 'Tuesday' ? 'selected' : ''}>Tuesday</option>
                            <option value="Wednesday" ${day === 'Wednesday' ? 'selected' : ''}>Wednesday</option>
                            <option value="Thursday" ${day === 'Thursday' ? 'selected' : ''}>Thursday</option>
                            <option value="Friday" ${day === 'Friday' ? 'selected' : ''}>Friday</option>
                            <option value="Saturday" ${day === 'Saturday' ? 'selected' : ''}>Saturday</option>
                        </select>
                    </div>
                    <div class="col-span-2">
                        <input type="number" min="0" max="23" value="${hour}" class="bulk-row-hour w-full bg-darkbg border border-gray-700 text-white rounded px-2 py-1 text-xs text-center" placeholder="Hour">
                    </div>
                    <div class="col-span-4">
                        <input type="text" value="${subject}" class="bulk-row-subject w-full bg-darkbg border border-gray-700 text-white rounded px-2 py-1 text-xs" placeholder="Subject Name">
                    </div>
                    <div class="col-span-2">
                        <input type="number" min="1" max="120" value="${windowMins}" class="bulk-row-window w-full bg-darkbg border border-gray-700 text-white rounded px-2 py-1 text-xs text-center">
                    </div>
                    <div class="col-span-1 text-center">
                        <button type="button" onclick="document.getElementById('${rowId}').remove()" class="text-red-400 hover:text-red-300">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                `;
                rowsContainer?.appendChild(rowDiv);
            }

            if (rowsContainer) {
                addBulkRow("Monday", 9, "Mathematics", 10);
                addBulkRow("Tuesday", 10, "Physics", 10);
                addBulkRow("Wednesday", 11, "Basic Electronics", 10);
            }

            document.getElementById('add-bulk-row-btn')?.addEventListener('click', () => addBulkRow("Monday", 9, "New Subject", 10));

            // Modal Trigger buttons
            const bulkBtn = document.getElementById('btn-bulk-upload-timetable');
            const bulkModal = document.getElementById('bulk-timetable-modal');
            const closeBulkBtn = document.getElementById('close-bulk-modal-btn');
            const cancelBulkBtn = document.getElementById('cancel-bulk-modal-btn');

            if (bulkBtn) bulkBtn.addEventListener('click', () => bulkModal.classList.remove('hidden'));
            if (closeBulkBtn) closeBulkBtn.addEventListener('click', () => bulkModal.classList.add('hidden'));
            if (cancelBulkBtn) cancelBulkBtn.addEventListener('click', () => bulkModal.classList.add('hidden'));

            // Manual Submit Form
            document.getElementById('bulk-timetable-form')?.addEventListener('submit', async (e) => {
                e.preventDefault();
                const teacherEmail = document.getElementById('bulk-teacher-email').value.trim();
                const section = document.getElementById('bulk-section').value.trim().toUpperCase();
                const rows = rowsContainer.querySelectorAll('[id^="row-"]');

                const entries = [];
                rows.forEach(r => {
                    const d = r.querySelector('.bulk-row-day').value;
                    const h = parseInt(r.querySelector('.bulk-row-hour').value, 10);
                    const subj = r.querySelector('.bulk-row-subject').value.trim();
                    const wm = parseInt(r.querySelector('.bulk-row-window').value, 10) || 10;
                    if (subj) {
                        entries.push({
                            day: d,
                            hour: h,
                            start_minute: 0,
                            allowed_window_minutes: wm,
                            subject: subj,
                            teacher_email: teacherEmail,
                            section: section,
                            branch_code: section ? section[0] : "",
                            year: section && section[1] && !isNaN(section[1]) ? parseInt(section[1], 10) : 0
                        });
                    }
                });

                try {
                    const res = await api.batchAddTimetable({ entries });
                    showToast(res.message || `Uploaded ${entries.length} weekly classes!`, "success");
                    bulkModal.classList.add('hidden');
                    await loadTimetable();
                } catch (err) {
                    showToast(`Bulk upload failed: ${err.message}`, "error");
                }
            });
        }

        // Filters and refresh handlers
        document.getElementById('btn-refresh-timetable').addEventListener('click', loadTimetable);
        document.getElementById('filter-day').addEventListener('change', () => {
            if (currentData) renderTable(currentData.timetable);
        });
        document.getElementById('filter-branch').addEventListener('change', () => {
            if (currentData) renderTable(currentData.timetable);
        });
        document.getElementById('filter-year').addEventListener('change', () => {
            if (currentData) renderTable(currentData.timetable);
        });

        if (isTeacherOrAdmin) {
            document.getElementById('add-timetable-form')?.addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = document.getElementById('btn-save-class');
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

                try {
                    const formData = new FormData(e.target);
                    const startTime = formData.get('start_time');
                    if (startTime) {
                        const [h, m] = startTime.split(':');
                        formData.append('hour', parseInt(h, 10));
                        formData.append('start_minute', parseInt(m, 10));
                    }
                    const endTime = formData.get('end_time');
                    if (endTime) {
                        const [h, m] = endTime.split(':');
                        formData.append('end_hour', parseInt(h, 10));
                        formData.append('end_minute', parseInt(m, 10));
                    }
                    const res = await api.addTimetableEntry(formData);
                    showToast(res.message || "Class schedule saved!", "success");
                    e.target.reset();
                    await loadTimetable();
                } catch (err) {
                    showToast(`Error saving class: ${err.message}`, "error");
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-save"></i> Save Class Schedule';
                }
            });
        }

        // Initial Load
        await loadTimetable();
    }
};
