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
        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-clock text-highlight"></i>
                        Class Timetable & Strict 10-Min Windows
                    </h2>
                    <p class="text-gray-400 mt-1">
                        Schedule classes branch-wise (A–G), academic year-wise (1st–4th Year), and section-wise with strict attendance windows.
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    <button id="btn-refresh-timetable" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-white rounded-lg border border-gray-600 flex items-center gap-2 text-sm font-semibold transition-colors">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                </div>
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
                        <i class="fas fa-calendar-plus text-highlight"></i>
                        Schedule Class
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

                        <!-- Branch & Year Selector -->
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
                            <span class="text-[11px] text-gray-400">Auto-filled based on selected Branch & Year</span>
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Start Time *</label>
                                <input type="time" id="tt-start-time" name="start_time" required 
                                    class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">End Time *</label>
                                <input type="time" id="tt-end-time" name="end_time" required 
                                    class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">
                                Attendance Window (Minutes)
                                <span class="text-[10px] text-highlight font-semibold ml-1">STRICT</span>
                            </label>
                            <input type="number" id="tt-window" name="allowed_window_minutes" min="1" max="60" value="10" required 
                                class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            <span class="text-[11px] text-gray-400">Late scans after this window will be rejected with 403 error.</span>
                        </div>

                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Subject / Course Name *</label>
                            <input type="text" id="tt-subject" name="subject" placeholder="e.g. Data Structures, Thermodynamics" required 
                                class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                        </div>

                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Teacher Email *</label>
                            <input type="email" id="tt-email" name="teacher_email" placeholder="e.g. prof@iert.ac.in" required 
                                class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" />
                            <span class="text-[11px] text-gray-500">Excel report with student roll list is emailed here.</span>
                        </div>

                        <button type="submit" id="btn-save-class" class="w-full py-2.5 bg-highlight hover:bg-pink-700 text-white font-semibold rounded-lg shadow-md transition-colors flex items-center justify-center gap-2 text-sm">
                            <i class="fas fa-save"></i> Save Class Schedule
                        </button>
                    </form>
                </div>

                <!-- Right: Full Timetable Table -->
                <div class="lg:col-span-2 bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-3">
                        <h3 class="text-xl font-bold text-white flex items-center gap-2">
                            <i class="fas fa-list-check text-highlight"></i>
                            Scheduled Classes
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
                                    <th class="py-3 px-3 text-center">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="timetable-tbody" class="divide-y divide-gray-700 text-xs">
                                <tr>
                                    <td colspan="7" class="py-8 text-center text-gray-500">Loading schedule...</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        let currentData = null;

        // Dynamic Section options generator for Form
        const updateFormSections = () => {
            const branch = document.getElementById('tt-branch').value;
            const year = parseInt(document.getElementById('tt-year').value || '0');
            const sectionSelect = document.getElementById('tt-section');
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

        document.getElementById('tt-branch').addEventListener('change', updateFormSections);
        document.getElementById('tt-year').addEventListener('change', updateFormSections);
        updateFormSections();

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
                            <div class="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center text-gray-400 text-xl">
                                <i class="fas fa-moon"></i>
                            </div>
                            <div>
                                <h4 class="text-base font-bold text-white">No Active Class Session Right Now</h4>
                                <p class="text-xs text-gray-400">Current Server Time: <span class="font-mono text-gray-300">${slot ? slot.day : ''} ${slot ? slot.time : ''}</span></p>
                            </div>
                        </div>
                        <span class="px-3 py-1 rounded-full bg-gray-700 text-gray-300 text-xs font-semibold">
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
                        <div class="w-14 h-14 rounded-full ${isWindowOpen ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'} flex items-center justify-center text-2xl border ${isWindowOpen ? 'border-green-500/40' : 'border-red-500/40'}">
                            <i class="fas ${isWindowOpen ? 'fa-door-open' : 'fa-door-closed'}"></i>
                        </div>
                        <div>
                            <div class="flex flex-wrap items-center gap-2">
                                <h4 class="text-xl font-bold text-white">${slot.class.subject}</h4>
                                <span class="px-2.5 py-0.5 rounded-full ${isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'} text-xs font-bold uppercase tracking-wider">
                                    ${isWindowOpen ? '● Attendance Window Open' : '● Window Expired'}
                                </span>
                                ${yearNum ? `<span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-semibold">${yearLabel}</span>` : ''}
                                ${section ? `<span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-mono font-semibold">Sec ${section}</span>` : ''}
                                ${branchCode ? `<span class="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 text-xs font-semibold">Branch ${branchCode}</span>` : ''}
                            </div>
                            <p class="text-xs text-gray-300 mt-1">
                                Teacher: <span class="text-gray-200">${slot.class.teacher_email}</span> | Server Time: <span class="font-mono text-highlight">${slot.time}</span>
                            </p>
                            <p class="text-xs text-gray-400 mt-0.5">
                                ${slot.window_status ? slot.window_status.message : ''}
                            </p>
                        </div>
                    </div>

                    <button id="btn-end-active-class" class="px-4 py-2.5 bg-accent hover:bg-blue-900 text-white text-xs font-semibold rounded-lg border border-blue-500/30 flex items-center gap-2 transition-colors shadow-md">
                        <i class="fas fa-file-excel text-green-400"></i> End Class & Email Sheet
                    </button>
                </div>
            `;

            const endBtn = document.getElementById('btn-end-active-class');
            if (endBtn) {
                endBtn.addEventListener('click', async () => {
                    const secText = section ? ` (Section ${section}, ${yearLabel})` : '';
                    if (!confirm(`Are you sure you want to end class for '${slot.class.subject}'${secText} and email the attendance report to ${slot.class.teacher_email}?`)) {
                        return;
                    }
                    endBtn.disabled = true;
                    endBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating & Emailing...';
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

                        showToast(res.message || `Attendance report generated!`, res.email_sent ? "success" : "info");
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
                tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-gray-500">No classes found for this filter.</td></tr>`;
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
                            <span class="inline-block mt-0.5 px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold">${yrLabel}</span>
                        </td>
                        <td class="py-3 px-3">
                            ${sec && sec !== 'All Sections' && sec !== 'All' ? `
                                <span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-mono font-bold">${sec}</span>
                            ` : `<span class="text-gray-500 text-xs">All</span>`}
                        </td>
                        <td class="py-3 px-3">
                            <span class="px-2 py-0.5 rounded-md bg-highlight/20 text-pink-300 border border-highlight/30 text-[11px] font-medium whitespace-nowrap">
                                ${item.attendance_window}
                            </span>
                        </td>
                        <td class="py-3 px-3">
                            <span class="font-medium text-white">${item.subject}</span>
                        </td>
                        <td class="py-3 px-3 text-gray-400 font-mono text-[11px]">${item.teacher_email}</td>
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
                    </tr>
                `;
            }).join('');

            // Delete Class handler
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

            // Quick Generate Sheet handler
            tbody.querySelectorAll('.btn-generate-class-sheet').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const subject = btn.getAttribute('data-subject');
                    const email = btn.getAttribute('data-email');
                    const branch = btn.getAttribute('data-branch') || '';
                    const year = btn.getAttribute('data-year') || '0';
                    const section = btn.getAttribute('data-section') || '';

                    if (!confirm(`Generate official Excel report for '${subject}' (${YEAR_MAP[year] || 'All Years'} - ${section || 'All Sections'}) and send to ${email}?`)) return;

                    btn.disabled = true;
                    try {
                        const fd = new FormData();
                        fd.append('subject', subject);
                        fd.append('teacher_email', email);
                        if (branch) fd.append('branch', branch);
                        if (year && year !== '0') fd.append('year', year);
                        if (section && section !== 'All' && section !== 'All Sections') fd.append('section', section);

                        const res = await api.endClass(fd);
                        if (res.download_url) {
                            const a = document.createElement('a');
                            a.href = res.download_url;
                            a.download = res.filename || `Attendance_${subject}.xlsx`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        }
                        showToast(res.message || `Attendance report generated!`, res.email_sent ? "success" : "info");
                    } catch (err) {
                        showToast(`Failed: ${err.message}`, "error");
                    } finally {
                        btn.disabled = false;
                    }
                });
            });
        };

        // Event listeners
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

        // Add class submit
        document.getElementById('add-timetable-form').addEventListener('submit', async (e) => {
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
                if (document.getElementById('tt-window')) {
                    document.getElementById('tt-window').value = '10';
                }
                updateFormSections();
                await loadTimetable();
            } catch (err) {
                showToast(`Error saving class: ${err.message}`, "error");
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-save"></i> Save Class Schedule';
            }
        });

        // Initial load
        await loadTimetable();
    }
};
