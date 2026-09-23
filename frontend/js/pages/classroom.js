import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    async render(container) {
        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white">Live Classroom Status</h2>
                    <p class="text-gray-400 mt-1 flex items-center gap-2">
                        <span class="flex h-2 w-2 relative">
                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                        </span>
                        Auto-refreshing live classroom feed
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    <button id="btn-refresh-live" class="px-4 py-2 bg-cardbg hover:bg-gray-700 text-white rounded-lg border border-gray-600 flex items-center gap-2 text-sm">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                    <a href="#timetable" class="px-4 py-2 bg-accent hover:bg-blue-900 text-white rounded-lg text-sm flex items-center gap-2">
                        <i class="fas fa-calendar-alt"></i> View Schedule
                    </a>
                </div>
            </div>

            <!-- Active Class Banner -->
            <div id="class-banner" class="bg-cardbg rounded-xl border border-gray-700 p-6 mb-6 shadow-lg">
                <div class="flex items-center justify-center py-4 text-gray-400">
                    <i class="fas fa-spinner fa-spin mr-2"></i> Loading current session...
                </div>
            </div>

            <!-- Stats Overview -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center">
                    <p class="text-gray-400 text-sm mb-1">Present Today</p>
                    <p id="stat-present" class="text-3xl font-bold text-green-400">0</p>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center">
                    <p class="text-gray-400 text-sm mb-1">Total Enrolled</p>
                    <p id="stat-total" class="text-3xl font-bold text-white">0</p>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 text-center col-span-2 md:col-span-2 flex flex-col justify-center">
                    <div class="w-full bg-gray-700 rounded-full h-4 mb-2">
                        <div id="attendance-progress" class="bg-highlight h-4 rounded-full transition-all duration-500" style="width: 0%"></div>
                    </div>
                    <p id="stat-percent" class="text-xs text-gray-400 text-right">0% Attendance Rate</p>
                </div>
            </div>

            <!-- Student Grid -->
            <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg min-h-[350px]">
                <div class="flex items-center justify-between mb-4 border-b border-gray-700 pb-3">
                    <h3 class="text-lg font-semibold text-white flex items-center gap-2">
                        <i class="fas fa-user-check text-green-400"></i> Present Students in Classroom
                    </h3>
                    <span id="badge-count" class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-700 text-gray-300">0 Students</span>
                </div>
                <div id="live-grid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    <div class="col-span-full py-12 text-center text-gray-500">
                        <i class="fas fa-spinner fa-spin text-3xl mb-3"></i>
                        <p>Loading attendance data...</p>
                    </div>
                </div>
            </div>
        `;

        const loadLiveStatus = async () => {
            const grid = document.getElementById('live-grid');
            const banner = document.getElementById('class-banner');
            const todayIso = new Date().toISOString().slice(0, 10);
            
            try {
                const [studentsRes, attendanceRes, timetableRes] = await Promise.all([
                    api.getStudents().catch(() => ({ students: [] })),
                    api.getAttendance('', todayIso).catch(() => ({ records: [] })),
                    api.getTimetable().catch(() => null)
                ]);

                const allStudents = studentsRes.students || studentsRes || [];
                const records = attendanceRes.records || attendanceRes || [];
                const totalCount = Array.isArray(allStudents) ? allStudents.length : 0;
                
                // Active slot banner
                const slot = timetableRes?.current_slot;
                if (slot && slot.class) {
                    const isWindowOpen = slot.window_status?.is_open;
                    banner.innerHTML = `
                        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                            <div>
                                <div class="flex items-center gap-3">
                                    <h3 class="text-xl font-bold text-white">${slot.class.subject}</h3>
                                    <span class="px-3 py-1 rounded-full text-xs font-bold uppercase ${isWindowOpen ? 'bg-green-500/20 text-green-400 border border-green-500/40' : 'bg-red-500/20 text-red-400 border border-red-500/40'}">
                                        ${isWindowOpen ? '● Window Open' : '● Window Closed'}
                                    </span>
                                </div>
                                <p class="text-sm text-gray-300 mt-1">
                                    Teacher: <span class="text-white">${slot.class.teacher_email}</span> | Server Time: <span class="font-mono text-highlight">${slot.time}</span>
                                </p>
                            </div>
                            <div class="flex items-center gap-3">
                                <button id="btn-live-end-class" class="bg-highlight hover:bg-red-600 text-white px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shadow">
                                    <i class="fas fa-file-excel"></i> End Class & Send Sheet
                                </button>
                                <span class="text-xs text-gray-400 font-mono bg-darkbg px-3 py-2 rounded-lg border border-gray-700">
                                    10-Min Allowed Window
                                </span>
                            </div>
                        </div>
                    `;

                    document.getElementById('btn-live-end-class')?.addEventListener('click', async () => {
                        const btn = document.getElementById('btn-live-end-class');
                        const origText = btn.innerHTML;
                        if (!confirm(`End class for '${slot.class.subject}' and email the attendance Excel sheet to ${slot.class.teacher_email}?`)) {
                            return;
                        }
                        try {
                            btn.disabled = true;
                            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Sending...';
                            const fd = new FormData();
                            fd.append('subject', slot.class.subject);
                            fd.append('teacher_email', slot.class.teacher_email);
                            const res = await api.endClass(fd);
                            showToast(res.message, "success");
                        } catch (err) {
                            showToast(`Failed: ${err.message}`, "error");
                        } finally {
                            btn.disabled = false;
                            btn.innerHTML = origText;
                        }
                    });
                } else {
                    banner.innerHTML = `
                        <div class="flex items-center justify-between text-gray-400">
                            <div class="flex items-center gap-3">
                                <i class="fas fa-coffee text-xl text-yellow-500"></i>
                                <span>No lecture currently in session.</span>
                            </div>
                            <span class="text-xs font-mono">${new Date().toLocaleTimeString()}</span>
                        </div>
                    `;
                }

                // Stats calculation
                const presentRecords = Array.isArray(records) ? records.filter(r => r.status === 'Present') : [];
                const presentCount = presentRecords.length;

                document.getElementById('stat-present').textContent = presentCount;
                document.getElementById('stat-total').textContent = totalCount;
                
                const pct = totalCount > 0 ? (presentCount / totalCount) * 100 : 0;
                document.getElementById('attendance-progress').style.width = `${pct}%`;
                document.getElementById('stat-percent').textContent = `${pct.toFixed(1)}% Attendance Rate`;
                document.getElementById('badge-count').textContent = `${presentCount} Present`;

                if (presentCount === 0) {
                    grid.innerHTML = `
                        <div class="col-span-full py-12 text-center text-gray-500">
                            <i class="fas fa-user-clock text-3xl mb-3 text-gray-600"></i>
                            <p>No students marked present yet today.</p>
                            <p class="text-xs text-gray-600 mt-1">Students will appear here as soon as they scan face on mobile app.</p>
                        </div>
                    `;
                    return;
                }

                grid.innerHTML = presentRecords.map(s => `
                    <div class="bg-gray-800 bg-opacity-50 border border-gray-700 rounded-lg p-4 flex flex-col items-center relative overflow-hidden group hover:border-highlight transition-colors">
                        <div class="absolute top-2 right-2 text-[10px] font-mono text-gray-400">${s.time}</div>
                        
                        <div class="w-13 h-13 rounded-full bg-accent flex items-center justify-center text-base font-bold text-white mb-2 shadow-inner">
                            ${s.name ? s.name.charAt(0).toUpperCase() : '?'}
                        </div>
                        
                        <h4 class="text-white font-medium text-center truncate w-full text-xs">${s.name || '-'}</h4>
                        <p class="text-[11px] text-gray-400 font-mono mb-1.5">${s.roll_no}</p>
                        
                        <div class="flex items-center gap-1 mb-2">
                            ${s.branch_code ? `<span class="px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold">${s.branch_code}</span>` : ''}
                            ${s.section ? `<span class="px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-300 font-mono text-[10px] font-bold">${s.section}</span>` : ''}
                        </div>

                        <div class="w-full flex items-center justify-between mt-auto pt-2 border-t border-gray-700 text-[11px]">
                            <span class="bg-gray-900 px-1.5 py-0.5 rounded text-gray-400 font-mono inline-flex items-center gap-1 text-[10px]">
                                <i class="fas fa-camera text-highlight text-[9px]"></i> Face
                            </span>
                            <span class="text-green-400 font-medium inline-flex items-center gap-1 text-[10px]">
                                <i class="fas fa-check-circle"></i> Verified
                            </span>
                        </div>
                    </div>
                `).join('');

            } catch (e) {
                console.error("Classroom live error:", e);
            }
        };

        document.getElementById('btn-refresh-live').addEventListener('click', loadLiveStatus);

        loadLiveStatus();
        const interval = setInterval(loadLiveStatus, 10000);
        if (window.currentIntervals) window.currentIntervals.push(interval);
    }
};

