import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    async render(container) {
        let activeClasses = [];
        let cachedRecords = [];
        let allStudents = [];
        let selectedClassIndex = 0; // Index of selected class, or -1 for All
        let currentSearchQuery = '';

        container.innerHTML = `
            <!-- Top Page Header -->
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-chalkboard text-highlight"></i> Live Classroom Status
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

            <!-- 1. Live Classes Cards (Click to Filter) -->
            <div class="mb-6">
                <div class="flex items-center justify-between mb-3">
                    <div>
                        <h3 class="text-sm font-semibold uppercase tracking-wider text-gray-300 flex items-center gap-2">
                            <i class="fas fa-broadcast-tower text-green-400"></i> Active Live Lectures
                        </h3>
                        <p class="text-xs text-gray-400 mt-0.5">Click any class below to see who has attended that particular lecture</p>
                    </div>
                    <span id="live-classes-count-badge" class="text-xs bg-green-900/60 text-green-300 border border-green-700 px-2.5 py-1 rounded-full font-mono font-semibold">
                        Scanning...
                    </span>
                </div>
                
                <div id="live-classes-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div class="col-span-full bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg text-center text-gray-400">
                        <i class="fas fa-spinner fa-spin mr-2"></i> Checking active live classes...
                    </div>
                </div>
            </div>

            <!-- 2. Selected Class Detail & Action Bar -->
            <div id="selected-class-banner" class="bg-cardbg rounded-xl border border-gray-700 p-5 mb-6 shadow-lg transition-all">
                <div class="text-center py-2 text-gray-400 text-sm">
                    Select a class above to view actions and attendance records.
                </div>
            </div>

            <!-- 3. Stats for Selected Class -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center shadow">
                    <p id="stat-present-label" class="text-gray-400 text-xs mb-1">Present in Selected Class</p>
                    <p id="stat-present" class="text-3xl font-bold text-green-400">0</p>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center shadow">
                    <p id="stat-enrolled-label" class="text-gray-400 text-xs mb-1">Section Enrolled</p>
                    <p id="stat-total" class="text-3xl font-bold text-white">0</p>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center col-span-2 md:col-span-2 flex flex-col justify-center shadow">
                    <div class="w-full bg-gray-700 rounded-full h-4 mb-2">
                        <div id="attendance-progress" class="bg-highlight h-4 rounded-full transition-all duration-500" style="width: 0%"></div>
                    </div>
                    <p id="stat-percent" class="text-xs text-gray-400 text-right font-medium">0% Attendance Rate</p>
                </div>
            </div>

            <!-- 4. Present Students Grid for Selected Class -->
            <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg min-h-[350px]">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 border-b border-gray-700 pb-3">
                    <div>
                        <h3 id="students-grid-title" class="text-lg font-semibold text-white flex items-center gap-2">
                            <i class="fas fa-user-check text-green-400"></i> Present Students in Classroom
                        </h3>
                        <p id="grid-filter-label" class="text-xs text-gray-400 mt-0.5">Students who marked attendance for this class</p>
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

        // Render the top active classes cards
        const renderClassesCards = () => {
            const gridEl = document.getElementById('live-classes-grid');
            const badgeEl = document.getElementById('live-classes-count-badge');

            if (!gridEl) return;

            if (activeClasses.length === 0) {
                if (badgeEl) badgeEl.textContent = '0 Live';
                gridEl.innerHTML = `
                    <div class="col-span-full bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-4">
                        <div class="flex items-center gap-3 text-gray-400">
                            <div class="w-10 h-10 rounded-full bg-yellow-500/10 flex items-center justify-center text-yellow-500">
                                <i class="fas fa-coffee text-lg"></i>
                            </div>
                            <div>
                                <p class="text-white font-semibold">No Lecture Currently Live</p>
                                <p class="text-xs text-gray-400">No classes are scheduled in the timetable for this hour.</p>
                            </div>
                        </div>
                        <a href="#timetable" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-gray-200 border border-gray-600 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors">
                            <i class="fas fa-calendar-alt"></i> View Schedule
                        </a>
                    </div>
                `;
                return;
            }

            if (badgeEl) badgeEl.textContent = `${activeClasses.length} Live Now`;

            // Draw cards for each active class
            let cardsHtml = activeClasses.map((cls, idx) => {
                const isSelected = selectedClassIndex === idx;
                const isWindowOpen = cls.window_status?.is_open;
                const timingStr = cls.timing_12h || cls.time_label || `${cls.hour || 0}:00`;
                const windowEndStr = cls.window_status?.window_end || cls.window_end_time || '';
                const sectionStr = cls.section && cls.section !== 'ALL' ? cls.section : 'All Sections';
                const branchStr = cls.branch_name || cls.branch_code || 'General';
                
                // Count how many students marked attendance for this subject/section
                const presentForThisClass = cachedRecords.filter(r => 
                    r.status === 'Present' && 
                    (r.subject || '').trim().toLowerCase() === (cls.subject || '').trim().toLowerCase()
                ).length;

                return `
                    <div data-class-index="${idx}" 
                         class="live-class-card rounded-xl p-4 transition-all cursor-pointer relative overflow-hidden select-none border-2 shadow-md hover:shadow-xl ${
                             isSelected 
                                ? 'bg-gradient-to-br from-cardbg to-[#1e293b] border-highlight ring-2 ring-highlight/50 shadow-highlight/20' 
                                : 'bg-cardbg/80 border-gray-700 hover:border-gray-500'
                         }">
                        
                        <!-- Top Row: Subject & Status -->
                        <div class="flex items-start justify-between gap-2 mb-2">
                            <div>
                                <h4 class="text-lg font-bold text-white uppercase tracking-wide flex items-center gap-2">
                                    ${cls.subject}
                                    ${isSelected ? '<span class="text-[10px] bg-highlight text-white px-2 py-0.5 rounded-full font-semibold">SELECTED</span>' : ''}
                                </h4>
                                <div class="flex items-center gap-1.5 mt-1">
                                    <span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-xs font-bold border border-blue-500/30">
                                        Sec ${sectionStr}
                                    </span>
                                    <span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-xs">
                                        ${branchStr}
                                    </span>
                                </div>
                            </div>

                            <span class="px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider whitespace-nowrap ${
                                isWindowOpen 
                                    ? 'bg-green-500/20 text-green-400 border border-green-500/40' 
                                    : 'bg-red-500/20 text-red-400 border border-red-500/40'
                            }">
                                ${isWindowOpen ? '● Window Open' : '● Window Closed'}
                            </span>
                        </div>

                        <!-- Class Timing & Window Info -->
                        <div class="space-y-1 my-3 text-xs text-gray-300 border-t border-b border-gray-700/60 py-2">
                            <div class="flex items-center justify-between">
                                <span class="text-gray-400"><i class="fas fa-clock text-highlight mr-1.5"></i> Timing:</span>
                                <span class="font-mono text-white font-semibold">${timingStr}</span>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-gray-400"><i class="fas fa-hourglass-half text-yellow-400 mr-1.5"></i> Window:</span>
                                <span class="font-mono ${isWindowOpen ? 'text-green-300 font-semibold' : 'text-gray-400'}">
                                    ${isWindowOpen ? `Until ${windowEndStr}` : 'Expired'}
                                </span>
                            </div>
                        </div>

                        <!-- Bottom Row: Present Count & Tap Action -->
                        <div class="flex items-center justify-between pt-1">
                            <div class="flex items-center gap-1.5 text-xs">
                                <span class="w-2.5 h-2.5 rounded-full bg-green-400"></span>
                                <span class="text-gray-300">Present:</span>
                                <span class="font-bold text-green-400 font-mono text-sm">${presentForThisClass}</span>
                            </div>
                            <span class="text-[11px] font-semibold text-highlight flex items-center gap-1">
                                ${isSelected ? 'Active View <i class="fas fa-check-circle"></i>' : 'Click to View <i class="fas fa-chevron-right"></i>'}
                            </span>
                        </div>
                    </div>
                `;
            }).join('');

            // Also add an "All Live Classes Combined" card if more than 1 class
            if (activeClasses.length > 1) {
                const isAllSelected = selectedClassIndex === -1;
                const totalLivePresent = cachedRecords.filter(r => r.status === 'Present').length;
                cardsHtml += `
                    <div data-class-index="-1" 
                         class="live-class-card rounded-xl p-4 transition-all cursor-pointer relative overflow-hidden select-none border-2 shadow-md hover:shadow-xl flex flex-col justify-between ${
                             isAllSelected 
                                ? 'bg-gradient-to-br from-cardbg to-[#1e293b] border-highlight ring-2 ring-highlight/50 shadow-highlight/20' 
                                : 'bg-cardbg/80 border-gray-700 hover:border-gray-500'
                         }">
                        <div>
                            <div class="flex items-start justify-between gap-2 mb-2">
                                <div>
                                    <h4 class="text-lg font-bold text-white uppercase tracking-wide flex items-center gap-2">
                                        All Live Classes
                                        ${isAllSelected ? '<span class="text-[10px] bg-highlight text-white px-2 py-0.5 rounded-full font-semibold">SELECTED</span>' : ''}
                                    </h4>
                                    <span class="text-xs text-gray-400 mt-1 block">View combined students from all sections</span>
                                </div>
                                <span class="px-2 py-0.5 rounded bg-gray-700 text-gray-300 text-xs font-mono">
                                    ${activeClasses.length} Classes
                                </span>
                            </div>
                        </div>

                        <div class="flex items-center justify-between pt-4 border-t border-gray-700/60 mt-3">
                            <div class="flex items-center gap-1.5 text-xs">
                                <span class="w-2.5 h-2.5 rounded-full bg-green-400"></span>
                                <span class="text-gray-300">Total Present:</span>
                                <span class="font-bold text-green-400 font-mono text-sm">${totalLivePresent}</span>
                            </div>
                            <span class="text-[11px] font-semibold text-highlight flex items-center gap-1">
                                ${isAllSelected ? 'Active View <i class="fas fa-check-circle"></i>' : 'Click to View <i class="fas fa-chevron-right"></i>'}
                            </span>
                        </div>
                    </div>
                `;
            }

            gridEl.innerHTML = cardsHtml;

            // Add click listeners to cards
            gridEl.querySelectorAll('.live-class-card').forEach(card => {
                card.addEventListener('click', () => {
                    const idx = parseInt(card.getAttribute('data-class-index'), 10);
                    selectedClassIndex = idx;
                    renderClassesCards();
                    renderSelectedClassBanner();
                    renderStats();
                    renderGrid();
                });
            });
        };

        // Render Action Banner for the selected class
        const renderSelectedClassBanner = () => {
            const bannerEl = document.getElementById('selected-class-banner');
            if (!bannerEl) return;

            if (activeClasses.length === 0) {
                bannerEl.innerHTML = `
                    <div class="flex items-center justify-between text-gray-400 text-xs">
                        <span>No active lecture selected.</span>
                        <span class="font-mono">${new Date().toLocaleTimeString()}</span>
                    </div>
                `;
                return;
            }

            if (selectedClassIndex === -1) {
                // All Classes mode
                bannerEl.innerHTML = `
                    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div>
                            <div class="flex items-center gap-3">
                                <h3 class="text-xl font-bold text-white">All Live Lectures (Combined View)</h3>
                                <span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40">
                                    ${activeClasses.length} Concurrent Classes
                                </span>
                            </div>
                            <p class="text-xs text-gray-400 mt-1">
                                Showing all students who checked into any live lecture right now.
                            </p>
                        </div>
                    </div>
                `;
                return;
            }

            const current = activeClasses[selectedClassIndex];
            if (!current) return;

            const isWindowOpen = current.window_status?.is_open;
            const timingStr = current.timing_12h || current.time_label || `${current.hour || 0}:00`;
            const windowLabel = current.attendance_window_label || current.attendance_window || `${current.allowed_window_minutes || 10} Min Window`;
            const sectionStr = current.section && current.section !== 'ALL' ? current.section : 'All Sections';
            const teacherStr = current.teacher_email || 'ayushpandey111223@gmail.com';

            bannerEl.innerHTML = `
                <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                    <div class="flex-1">
                        <div class="flex flex-wrap items-center gap-2.5 mb-1.5">
                            <span class="text-xs text-gray-400 font-semibold">CURRENTLY VIEWING:</span>
                            <h3 class="text-2xl font-bold text-white uppercase">${current.subject}</h3>
                            <span class="px-2.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-xs font-bold border border-blue-500/30">
                                Section ${sectionStr}
                            </span>
                            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${
                                isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'
                            }">
                                ${isWindowOpen ? '● Window Open' : '● Window Closed'}
                            </span>
                        </div>
                        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-300 mt-1">
                            <span><i class="fas fa-clock text-highlight mr-1"></i> Class Timing: <strong class="text-white">${timingStr}</strong></span>
                            <span><i class="fas fa-hourglass-half text-yellow-400 mr-1"></i> Attendance Window: <strong class="text-white">${windowLabel}</strong></span>
                            <span><i class="fas fa-envelope text-blue-400 mr-1"></i> Teacher: <strong class="text-white">${teacherStr}</strong></span>
                        </div>
                    </div>

                    <!-- Related Action Buttons -->
                    <div class="flex flex-wrap items-center gap-2.5 w-full lg:w-auto pt-2 lg:pt-0 border-t lg:border-t-0 border-gray-700">
                        <button id="btn-download-selected-sheet" 
                                class="px-4 py-2 bg-accent hover:bg-blue-900 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors border border-blue-600 shadow">
                            <i class="fas fa-download"></i> Download Excel
                        </button>
                        <button id="btn-end-selected-class" 
                                class="px-4 py-2 bg-highlight hover:bg-red-600 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shadow">
                            <i class="fas fa-file-excel"></i> End Class & Send Sheet
                        </button>
                    </div>
                </div>
            `;

            // Wire action buttons
            document.getElementById('btn-download-selected-sheet')?.addEventListener('click', async () => {
                const btn = document.getElementById('btn-download-selected-sheet');
                const origText = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Generating...';
                try {
                    const fd = new FormData();
                    fd.append('subject', current.subject);
                    if (current.section) fd.append('section', current.section);
                    if (current.branch_code) fd.append('branch_code', current.branch_code);
                    const res = await api.endClass(fd);
                    if (res.download_url) {
                        window.open(res.download_url, '_blank');
                        showToast(`Excel attendance sheet for '${current.subject}' downloaded!`, 'success');
                    } else {
                        showToast(res.message || 'Sheet generated.', 'success');
                    }
                } catch (err) {
                    showToast(`Failed to generate sheet: ${err.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = origText;
                }
            });

            document.getElementById('btn-end-selected-class')?.addEventListener('click', async () => {
                const btn = document.getElementById('btn-end-selected-class');
                const teacher = current.teacher_email || '';
                const confirmMsg = teacher
                    ? `End class for '${current.subject}' (Sec ${sectionStr}) and email attendance sheet to ${teacher}?`
                    : `End class for '${current.subject}' (Sec ${sectionStr}) and generate attendance sheet?`;

                if (!confirm(confirmMsg)) return;

                const origText = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Ending & Sending...';
                try {
                    const fd = new FormData();
                    fd.append('subject', current.subject);
                    if (teacher) fd.append('teacher_email', teacher);
                    if (current.section) fd.append('section', current.section);
                    if (current.branch_code) fd.append('branch_code', current.branch_code);

                    const res = await api.endClass(fd);
                    showToast(res.message || `Class '${current.subject}' ended successfully!`, 'success');
                    if (res.download_url) {
                        window.open(res.download_url, '_blank');
                    }
                } catch (err) {
                    showToast(`Failed: ${err.message}`, 'error');
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = origText;
                }
            });
        };

        // Render attendance numbers and rate
        const renderStats = () => {
            let presentCount = 0;
            let enrolledCount = 0;

            if (selectedClassIndex === -1) {
                // All Classes mode
                presentCount = cachedRecords.filter(r => r.status === 'Present').length;
                enrolledCount = allStudents.length;
                document.getElementById('stat-present-label').textContent = 'Total Present (All Live Classes)';
                document.getElementById('stat-enrolled-label').textContent = 'Total Enrolled Students';
            } else if (activeClasses[selectedClassIndex]) {
                const current = activeClasses[selectedClassIndex];
                const cleanSubj = (current.subject || '').trim().toLowerCase();
                const cleanSec = (current.section || '').trim().toUpperCase();

                presentCount = cachedRecords.filter(r => 
                    r.status === 'Present' && 
                    (r.subject || '').trim().toLowerCase() === cleanSubj
                ).length;

                if (cleanSec && cleanSec !== 'ALL' && cleanSec !== 'ALL SECTIONS') {
                    enrolledCount = allStudents.filter(s => (s.section || '').trim().toUpperCase() === cleanSec).length;
                    document.getElementById('stat-enrolled-label').textContent = `Enrolled in Section ${cleanSec}`;
                } else {
                    enrolledCount = allStudents.length;
                    document.getElementById('stat-enrolled-label').textContent = 'Total Enrolled Students';
                }

                document.getElementById('stat-present-label').textContent = `Present in ${current.subject}`;
            }

            document.getElementById('stat-present').textContent = presentCount;
            document.getElementById('stat-total').textContent = enrolledCount || allStudents.length;

            const baseTotal = enrolledCount > 0 ? enrolledCount : (allStudents.length || 1);
            const pct = (presentCount / baseTotal) * 100;
            document.getElementById('attendance-progress').style.width = `${Math.min(100, pct)}%`;
            document.getElementById('stat-percent').textContent = `${pct.toFixed(1)}% Attendance Rate`;
        };

        // Render the students grid filtered strictly to the selected class
        const renderGrid = () => {
            const grid = document.getElementById('live-grid');
            const titleEl = document.getElementById('students-grid-title');
            const filterLabel = document.getElementById('grid-filter-label');
            const badgeCount = document.getElementById('badge-count');

            if (!grid) return;

            let filtered = cachedRecords.filter(r => r.status === 'Present');
            let currentClassSubject = '';
            let currentClassSection = '';

            if (selectedClassIndex >= 0 && activeClasses[selectedClassIndex]) {
                const cur = activeClasses[selectedClassIndex];
                currentClassSubject = cur.subject;
                currentClassSection = cur.section;
                const cleanSubj = (cur.subject || '').trim().toLowerCase();
                filtered = filtered.filter(r => (r.subject || '').trim().toLowerCase() === cleanSubj);
                
                if (titleEl) {
                    titleEl.innerHTML = `<i class="fas fa-user-check text-green-400"></i> Present Students in: <span class="text-highlight uppercase">${currentClassSubject}</span> (Sec ${cur.section || 'All'})`;
                }
                if (filterLabel) {
                    filterLabel.textContent = `Showing students who checked into '${currentClassSubject}'`;
                }
            } else {
                if (titleEl) {
                    titleEl.innerHTML = `<i class="fas fa-user-check text-green-400"></i> Present Students in Classroom (All Live Lectures)`;
                }
                if (filterLabel) {
                    filterLabel.textContent = `Showing students present across all live classes today`;
                }
            }

            // Apply search filter if typed
            const q = currentSearchQuery.trim().toLowerCase();
            if (q) {
                filtered = filtered.filter(r => 
                    (r.name || '').toLowerCase().includes(q) ||
                    (r.roll_no || '').toLowerCase().includes(q) ||
                    (r.section || '').toLowerCase().includes(q)
                );
            }

            if (badgeCount) badgeCount.textContent = `${filtered.length} Present`;

            if (filtered.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-full py-12 text-center text-gray-500">
                        <div class="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mx-auto mb-3 text-gray-600">
                            <i class="fas fa-user-clock text-2xl"></i>
                        </div>
                        <p class="font-medium text-gray-300">No students checked into this lecture yet.</p>
                        <p class="text-xs text-gray-500 mt-1">When students in Section ${currentClassSection || ''} scan their face in the mobile app, they will instantly appear here!</p>
                    </div>
                `;
                return;
            }

            grid.innerHTML = filtered.map(s => `
                <div class="bg-gray-800/70 border border-gray-700/80 hover:border-highlight rounded-xl p-3.5 flex flex-col items-center relative overflow-hidden group transition-all shadow hover:shadow-lg">
                    <div class="absolute top-2 right-2 text-[10px] font-mono text-gray-400 bg-gray-900/90 px-1.5 py-0.5 rounded border border-gray-700/40">
                        ${s.time || ''}
                    </div>
                    
                    <div class="w-12 h-12 rounded-full bg-accent flex items-center justify-center text-sm font-bold text-white mb-2 shadow-inner border border-blue-400/30">
                        ${s.name ? s.name.charAt(0).toUpperCase() : '?'}
                    </div>
                    
                    <h4 class="text-white font-medium text-center truncate w-full text-xs font-semibold" title="${s.name || ''}">${s.name || '-'}</h4>
                    <p class="text-[11px] text-gray-400 font-mono mb-1.5">${s.roll_no}</p>
                    
                    <div class="flex items-center gap-1 mb-2">
                        ${s.branch_code ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold">${s.branch_code}</span>` : ''}
                        ${s.section ? `<span class="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-[10px] font-bold">${s.section}</span>` : ''}
                        ${s.subject ? `<span class="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 text-[10px] font-semibold truncate max-w-[80px]" title="${s.subject}">${s.subject}</span>` : ''}
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
            const serverTimeEl = document.getElementById('header-server-time');
            const todayIso = new Date().toISOString().slice(0, 10);
            
            try {
                const [studentsRes, attendanceRes, timetableRes] = await Promise.all([
                    api.getStudents().catch(() => ({ students: [] })),
                    api.getAttendance('', todayIso).catch(() => ({ records: [] })),
                    api.getTimetable().catch(() => null)
                ]);

                allStudents = studentsRes.students || studentsRes || [];
                cachedRecords = attendanceRes.records || attendanceRes || [];
                
                const currentSlot = timetableRes?.current_slot;
                const serverTimeStr = currentSlot?.time || new Date().toLocaleTimeString();
                if (serverTimeEl) serverTimeEl.textContent = serverTimeStr;

                // Live classes resolution: use live_classes array or fallback to single class
                if (Array.isArray(currentSlot?.live_classes) && currentSlot.live_classes.length > 0) {
                    activeClasses = currentSlot.live_classes;
                } else if (currentSlot?.class) {
                    const single = { ...currentSlot.class };
                    single.window_status = currentSlot.window_status || {};
                    activeClasses = [single];
                } else {
                    activeClasses = [];
                }

                // If selectedClassIndex is out of range, default to 0
                if (selectedClassIndex >= activeClasses.length) {
                    selectedClassIndex = activeClasses.length > 0 ? 0 : -1;
                }

                renderClassesCards();
                renderSelectedClassBanner();
                renderStats();
                renderGrid();

            } catch (e) {
                console.error("Classroom live error:", e);
            }
        };

        document.getElementById('btn-refresh-live')?.addEventListener('click', loadLiveStatus);
        document.getElementById('live-search-input')?.addEventListener('input', (e) => {
            currentSearchQuery = e.target.value;
            renderGrid();
        });

        loadLiveStatus();
        const interval = setInterval(loadLiveStatus, 10000);
        if (window.currentIntervals) window.currentIntervals.push(interval);
    }
};
