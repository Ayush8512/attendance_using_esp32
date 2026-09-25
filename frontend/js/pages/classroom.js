import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    async render(container) {
        let selectedFilterClass = 'ALL';

        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-satellite-dish text-highlight"></i> Live Classroom Status
                    </h2>
                    <p class="text-gray-400 mt-1 flex items-center gap-2 text-sm">
                        <span class="flex h-2.5 w-2.5 relative">
                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                        </span>
                        Auto-refreshing live classroom feed &bull; Server Time: <span id="header-server-time" class="font-mono text-highlight font-semibold">--:--:--</span>
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    <button id="btn-refresh-live" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-white rounded-lg border border-gray-600 flex items-center gap-2 text-sm shadow transition-colors">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                    <a href="#timetable" class="px-4 py-2 bg-accent hover:bg-blue-900 text-white rounded-lg text-sm flex items-center gap-2 shadow transition-colors">
                        <i class="fas fa-calendar-alt"></i> View Schedule
                    </a>
                </div>
            </div>

            <!-- Active Live Classes Container -->
            <div class="mb-6">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-sm font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-2">
                        <i class="fas fa-chalkboard-teacher text-highlight"></i> Currently Live Classes & Options
                    </h3>
                    <span id="live-classes-count" class="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full font-mono">0 Active</span>
                </div>
                <div id="live-classes-list" class="space-y-4">
                    <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg text-center text-gray-400">
                        <i class="fas fa-spinner fa-spin mr-2"></i> Checking active class schedule...
                    </div>
                </div>
            </div>

            <!-- Stats Overview -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center shadow">
                    <p class="text-gray-400 text-sm mb-1">Present Today</p>
                    <p id="stat-present" class="text-3xl font-bold text-green-400">0</p>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center shadow">
                    <p class="text-gray-400 text-sm mb-1">Total Enrolled</p>
                    <p id="stat-total" class="text-3xl font-bold text-white">0</p>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center col-span-2 md:col-span-2 flex flex-col justify-center shadow">
                    <div class="w-full bg-gray-700 rounded-full h-4 mb-2">
                        <div id="attendance-progress" class="bg-highlight h-4 rounded-full transition-all duration-500" style="width: 0%"></div>
                    </div>
                    <p id="stat-percent" class="text-xs text-gray-400 text-right font-medium">0% Attendance Rate</p>
                </div>
            </div>

            <!-- Student Grid -->
            <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg min-h-[350px]">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 border-b border-gray-700 pb-3">
                    <div>
                        <h3 class="text-lg font-semibold text-white flex items-center gap-2">
                            <i class="fas fa-user-check text-green-400"></i> Present Students in Classroom
                        </h3>
                        <p id="grid-filter-label" class="text-xs text-gray-400 mt-0.5">Showing all students present today</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <input type="text" id="live-search-input" placeholder="Search name or roll no..." 
                               class="bg-darkbg border border-gray-600 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-highlight w-48 sm:w-60" />
                        <span id="badge-count" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-700 text-gray-300">0 Present</span>
                    </div>
                </div>
                <div id="live-grid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    <div class="col-span-full py-12 text-center text-gray-500">
                        <i class="fas fa-spinner fa-spin text-3xl mb-3"></i>
                        <p>Loading attendance data...</p>
                    </div>
                </div>
            </div>
        `;

        let cachedRecords = [];

        const renderGrid = () => {
            const grid = document.getElementById('live-grid');
            const searchVal = (document.getElementById('live-search-input')?.value || '').trim().toLowerCase();
            
            let filtered = cachedRecords.filter(r => r.status === 'Present');

            if (selectedFilterClass !== 'ALL') {
                filtered = filtered.filter(r => (r.subject || '').toUpperCase() === selectedFilterClass.toUpperCase());
            }

            if (searchVal) {
                filtered = filtered.filter(r => 
                    (r.name || '').toLowerCase().includes(searchVal) ||
                    (r.roll_no || '').toLowerCase().includes(searchVal) ||
                    (r.section || '').toLowerCase().includes(searchVal)
                );
            }

            document.getElementById('badge-count').textContent = `${filtered.length} Present`;

            if (filtered.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-full py-12 text-center text-gray-500">
                        <i class="fas fa-user-clock text-3xl mb-3 text-gray-600"></i>
                        <p class="font-medium text-gray-400">No students found matching current filters.</p>
                        <p class="text-xs text-gray-600 mt-1">Students will appear here as soon as they scan face on the mobile app.</p>
                    </div>
                `;
                return;
            }

            grid.innerHTML = filtered.map(s => `
                <div class="bg-gray-800 bg-opacity-60 border border-gray-700 rounded-lg p-3.5 flex flex-col items-center relative overflow-hidden group hover:border-highlight transition-all shadow hover:shadow-md">
                    <div class="absolute top-2 right-2 text-[10px] font-mono text-gray-400 bg-gray-900/80 px-1.5 py-0.5 rounded">${s.time || ''}</div>
                    
                    <div class="w-12 h-12 rounded-full bg-accent flex items-center justify-center text-sm font-bold text-white mb-2 shadow-inner border border-blue-400/30">
                        ${s.name ? s.name.charAt(0).toUpperCase() : '?'}
                    </div>
                    
                    <h4 class="text-white font-medium text-center truncate w-full text-xs" title="${s.name || ''}">${s.name || '-'}</h4>
                    <p class="text-[11px] text-gray-400 font-mono mb-1.5">${s.roll_no}</p>
                    
                    <div class="flex items-center gap-1 mb-2">
                        ${s.branch_code ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold">${s.branch_code}</span>` : ''}
                        ${s.section ? `<span class="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-[10px] font-bold">${s.section}</span>` : ''}
                        ${s.subject ? `<span class="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 text-[10px] truncate max-w-[80px]" title="${s.subject}">${s.subject}</span>` : ''}
                    </div>

                    <div class="w-full flex items-center justify-between mt-auto pt-2 border-t border-gray-700/60 text-[11px]">
                        <span class="bg-gray-900 px-1.5 py-0.5 rounded text-gray-400 font-mono inline-flex items-center gap-1 text-[10px]">
                            <i class="fas fa-camera text-highlight text-[9px]"></i> Face
                        </span>
                        <span class="text-green-400 font-medium inline-flex items-center gap-1 text-[10px]">
                            <i class="fas fa-check-circle"></i> Verified
                        </span>
                    </div>
                </div>
            `).join('');
        };

        const loadLiveStatus = async () => {
            const listContainer = document.getElementById('live-classes-list');
            const serverTimeEl = document.getElementById('header-server-time');
            const todayIso = new Date().toISOString().slice(0, 10);
            
            try {
                const [studentsRes, attendanceRes, timetableRes] = await Promise.all([
                    api.getStudents().catch(() => ({ students: [] })),
                    api.getAttendance('', todayIso).catch(() => ({ records: [] })),
                    api.getTimetable().catch(() => null)
                ]);

                const allStudents = studentsRes.students || studentsRes || [];
                cachedRecords = attendanceRes.records || attendanceRes || [];
                const totalCount = Array.isArray(allStudents) ? allStudents.length : 0;
                
                const currentSlot = timetableRes?.current_slot;
                const serverTimeStr = currentSlot?.time || new Date().toLocaleTimeString();
                if (serverTimeEl) serverTimeEl.textContent = serverTimeStr;

                // Live classes resolution: use live_classes array or fallback to single class
                let activeClasses = [];
                if (Array.isArray(currentSlot?.live_classes) && currentSlot.live_classes.length > 0) {
                    activeClasses = currentSlot.live_classes;
                } else if (currentSlot?.class) {
                    const single = { ...currentSlot.class };
                    single.window_status = currentSlot.window_status || {};
                    activeClasses = [single];
                }

                document.getElementById('live-classes-count').textContent = `${activeClasses.length} Active`;

                if (activeClasses.length === 0) {
                    listContainer.innerHTML = `
                        <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-4">
                            <div class="flex items-center gap-3 text-gray-400">
                                <div class="w-10 h-10 rounded-full bg-yellow-500/10 flex items-center justify-center text-yellow-500">
                                    <i class="fas fa-coffee text-lg"></i>
                                </div>
                                <div>
                                    <p class="text-white font-semibold">No Lecture Currently in Session</p>
                                    <p class="text-xs text-gray-400">Current server time: ${serverTimeStr}. Check schedule to see upcoming slots.</p>
                                </div>
                            </div>
                            <a href="#timetable" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-gray-200 border border-gray-600 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors">
                                <i class="fas fa-calendar-alt"></i> View All Timetables
                            </a>
                        </div>
                    `;
                } else {
                    listContainer.innerHTML = activeClasses.map((cls, idx) => {
                        const isWindowOpen = cls.window_status?.is_open;
                        const windowMsg = cls.window_status?.message || (isWindowOpen ? 'Window Open' : 'Window Closed');
                        const timingStr = cls.timing_12h || cls.time_label || `${cls.hour || 0}:00 - ${(cls.hour || 0) + 1}:00`;
                        const windowLabel = cls.attendance_window_label || cls.attendance_window || `${cls.allowed_window_minutes || 10} Min Window`;
                        const sectionStr = cls.section && cls.section !== 'ALL' ? cls.section : 'All Sections';
                        const branchStr = cls.branch_name || cls.branch_code || 'General';
                        const teacherStr = cls.teacher_email || 'Teacher Not Assigned';
                        const isFiltered = selectedFilterClass === (cls.subject || '').toUpperCase();

                        return `
                            <div class="bg-cardbg rounded-xl border ${isFiltered ? 'border-highlight ring-1 ring-highlight' : 'border-gray-700'} p-5 shadow-lg transition-all">
                                <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                                    <div class="flex-1">
                                        <div class="flex flex-wrap items-center gap-2.5 mb-2">
                                            <h3 class="text-xl font-bold text-white">${cls.subject}</h3>
                                            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'}">
                                                ${isWindowOpen ? '● Window Open' : '● Window Closed'}
                                            </span>
                                            <span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-xs font-bold">
                                                Sec: ${sectionStr}
                                            </span>
                                            <span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-xs">
                                                ${branchStr}
                                            </span>
                                        </div>

                                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs text-gray-300 mt-2">
                                            <div class="flex items-center gap-2">
                                                <i class="fas fa-clock text-highlight"></i>
                                                <span><strong>Class Timing:</strong> <span class="font-mono text-white">${timingStr}</span></span>
                                            </div>
                                            <div class="flex items-center gap-2">
                                                <i class="fas fa-hourglass-half text-yellow-400"></i>
                                                <span><strong>Allowed Window:</strong> <span class="font-mono text-gray-300">${windowLabel}</span></span>
                                            </div>
                                            <div class="flex items-center gap-2">
                                                <i class="fas fa-chalkboard-teacher text-blue-400"></i>
                                                <span><strong>Teacher:</strong> <span class="text-white">${teacherStr}</span></span>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Action Options -->
                                    <div class="flex flex-wrap items-center gap-2.5 w-full lg:w-auto pt-2 lg:pt-0 border-t lg:border-t-0 border-gray-700">
                                        <button data-action="filter-class" data-subject="${cls.subject}" 
                                                class="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${isFiltered ? 'bg-highlight text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-600'}">
                                            <i class="fas ${isFiltered ? 'fa-check' : 'fa-filter'}"></i>
                                            ${isFiltered ? 'Filtering Students' : 'View Students'}
                                        </button>

                                        <button data-action="download-sheet" data-subject="${cls.subject}" data-teacher="${cls.teacher_email || ''}" data-section="${cls.section || ''}" data-branch="${cls.branch_code || ''}"
                                                class="px-3 py-2 bg-accent hover:bg-blue-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors border border-blue-600 shadow">
                                            <i class="fas fa-download"></i> Download Sheet
                                        </button>

                                        <button data-action="end-class" data-subject="${cls.subject}" data-teacher="${cls.teacher_email || ''}" data-section="${cls.section || ''}" data-branch="${cls.branch_code || ''}"
                                                class="px-3 py-2 bg-highlight hover:bg-red-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow">
                                            <i class="fas fa-file-excel"></i> End Class & Send Sheet
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('');

                    // Wire action buttons
                    listContainer.querySelectorAll('[data-action="filter-class"]').forEach(btn => {
                        btn.addEventListener('click', () => {
                            const subj = btn.getAttribute('data-subject');
                            selectedFilterClass = (selectedFilterClass === subj.toUpperCase()) ? 'ALL' : subj.toUpperCase();
                            const filterLabel = document.getElementById('grid-filter-label');
                            if (filterLabel) {
                                filterLabel.textContent = selectedFilterClass === 'ALL' 
                                    ? 'Showing all students present today' 
                                    : `Showing students present for: ${subj}`;
                            }
                            loadLiveStatus();
                        });
                    });

                    listContainer.querySelectorAll('[data-action="download-sheet"]').forEach(btn => {
                        btn.addEventListener('click', async () => {
                            const subj = btn.getAttribute('data-subject');
                            const sec = btn.getAttribute('data-section');
                            const br = btn.getAttribute('data-branch');
                            const origText = btn.innerHTML;
                            btn.disabled = true;
                            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Generating...';
                            try {
                                const fd = new FormData();
                                fd.append('subject', subj);
                                if (sec) fd.append('section', sec);
                                if (br) fd.append('branch_code', br);
                                const res = await api.endClass(fd);
                                if (res.download_url) {
                                    window.open(res.download_url, '_blank');
                                    showToast(`Excel attendance sheet for '${subj}' downloaded!`, 'success');
                                } else {
                                    showToast(res.message || 'Sheet generated.', 'success');
                                }
                            } catch (err) {
                                showToast(`Failed: ${err.message}`, 'error');
                            } finally {
                                btn.disabled = false;
                                btn.innerHTML = origText;
                            }
                        });
                    });

                    listContainer.querySelectorAll('[data-action="end-class"]').forEach(btn => {
                        btn.addEventListener('click', async () => {
                            const subj = btn.getAttribute('data-subject');
                            const teacher = btn.getAttribute('data-teacher');
                            const sec = btn.getAttribute('data-section');
                            const br = btn.getAttribute('data-branch');
                            const confirmMsg = teacher 
                                ? `End class for '${subj}' and email the attendance Excel sheet to ${teacher}?`
                                : `End class for '${subj}' and generate the attendance Excel sheet?`;

                            if (!confirm(confirmMsg)) return;

                            const origText = btn.innerHTML;
                            btn.disabled = true;
                            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Sending...';
                            try {
                                const fd = new FormData();
                                fd.append('subject', subj);
                                if (teacher) fd.append('teacher_email', teacher);
                                if (sec) fd.append('section', sec);
                                if (br) fd.append('branch_code', br);

                                const res = await api.endClass(fd);
                                showToast(res.message || `Class ended and attendance sheet created!`, 'success');
                                if (res.download_url) {
                                    window.open(res.download_url, '_blank');
                                }
                            } catch (err) {
                                showToast(`Failed to end class: ${err.message}`, 'error');
                            } finally {
                                btn.disabled = false;
                                btn.innerHTML = origText;
                            }
                        });
                    });
                }

                // Stats calculation
                const presentRecords = Array.isArray(cachedRecords) ? cachedRecords.filter(r => r.status === 'Present') : [];
                const presentCount = presentRecords.length;

                document.getElementById('stat-present').textContent = presentCount;
                document.getElementById('stat-total').textContent = totalCount;
                
                const pct = totalCount > 0 ? (presentCount / totalCount) * 100 : 0;
                document.getElementById('attendance-progress').style.width = `${pct}%`;
                document.getElementById('stat-percent').textContent = `${pct.toFixed(1)}% Attendance Rate`;

                renderGrid();

            } catch (e) {
                console.error("Classroom live error:", e);
            }
        };

        document.getElementById('btn-refresh-live')?.addEventListener('click', loadLiveStatus);
        document.getElementById('live-search-input')?.addEventListener('input', renderGrid);

        loadLiveStatus();
        const interval = setInterval(loadLiveStatus, 10000);
        if (window.currentIntervals) window.currentIntervals.push(interval);
    }
};
