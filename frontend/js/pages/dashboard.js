import { api } from '../api.js';

export default {
    async render(container) {
        const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        const todayIso = new Date().toISOString().slice(0, 10);
        
        let stats = { 
            totalEnrolled: 1706, 
            registeredBiometrics: 0, 
            presentToday: 0, 
            activeClass: null, 
            health: 'Offline' 
        };
        let recent = [];
        
        try {
            const [studentsRes, healthRes, attendanceRes, timetableRes, rosterStatsRes] = await Promise.allSettled([
                api.getStudents(),
                api.healthCheck(),
                api.getAttendance(),
                api.getTimetable(),
                api.getRosterStats()
            ]);

            if (rosterStatsRes.status === 'fulfilled' && rosterStatsRes.value?.total_roster) {
                stats.totalEnrolled = rosterStatsRes.value.total_roster;
                stats.registeredBiometrics = rosterStatsRes.value.total_registered || 0;
            } else if (studentsRes.status === 'fulfilled') {
                const studentsList = studentsRes.value.students || studentsRes.value || [];
                stats.registeredBiometrics = Array.isArray(studentsList) ? studentsList.length : 0;
            }

            if (healthRes.status === 'fulfilled' && healthRes.value.status === 'healthy') {
                stats.health = 'Online';
            }

            if (timetableRes.status === 'fulfilled' && timetableRes.value.current_slot?.class) {
                stats.activeClass = timetableRes.value.current_slot;
            }

            if (attendanceRes.status === 'fulfilled') {
                const records = attendanceRes.value.records || attendanceRes.value || [];
                if (Array.isArray(records)) {
                    const todayRecords = records.filter(r => r.date === todayIso);
                    const uniquePresentToday = new Set(todayRecords.map(r => r.roll_no));
                    stats.presentToday = uniquePresentToday.size;
                    recent = records.slice(0, 8);
                }
            }
        } catch (e) {
            console.error("Error fetching stats", e);
        }

        const isClassActive = !!stats.activeClass?.class;
        const activeSub = isClassActive ? stats.activeClass.class.subject : 'No Active Class';
        const isWindowOpen = isClassActive && stats.activeClass.window_status?.is_open;

        container.innerHTML = `
            <!-- Dashboard Page Header -->
            <div class="mb-4 sm:mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-gray-700/60 pb-3 sm:pb-4">
                <div>
                    <h2 class="text-xl sm:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        <i class="fas fa-chart-line text-blue-500 sm:hidden"></i>
                        Campus Attendance Overview
                    </h2>
                    <p class="text-gray-400 text-xs sm:text-sm mt-0.5">IERT Prayagraj &bull; ${dateStr}</p>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <button id="refresh-dashboard" class="flex-1 sm:flex-initial justify-center bg-cardbg border border-gray-600 hover:border-blue-500 text-gray-200 hover:text-white px-3 sm:px-3.5 py-2 rounded-lg transition-colors flex items-center gap-2 text-xs font-semibold shadow-sm active:scale-95 touch-manipulation">
                        <i class="fas fa-sync-alt"></i> Refresh Data
                    </button>
                    <a href="#classroom" class="flex-1 sm:flex-initial justify-center bg-blue-600 hover:bg-blue-700 text-white px-3 sm:px-3.5 py-2 rounded-lg transition-colors flex items-center gap-2 text-xs font-semibold shadow-sm active:scale-95 touch-manipulation">
                        <i class="fas fa-bolt text-yellow-300"></i> Live Class
                    </a>
                </div>
            </div>

            <!-- Stats Grid: 2 columns on mobile, 4 columns on large screens -->
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-4 mb-5 sm:mb-6">
                <!-- 1. Enrolled Roster -->
                <div class="bg-cardbg rounded-xl p-3 sm:p-5 border border-gray-700/80 shadow-sm flex flex-col justify-between">
                    <div class="flex items-start justify-between gap-1">
                        <div class="min-w-0">
                            <p class="text-[10px] sm:text-xs font-semibold text-gray-400 uppercase tracking-wider truncate mb-0.5 sm:mb-1">Enrolled</p>
                            <h3 class="text-xl sm:text-2xl font-bold text-white font-mono leading-none">${stats.totalEnrolled.toLocaleString()}</h3>
                        </div>
                        <div class="w-8 h-8 sm:w-11 sm:h-11 bg-blue-900/30 rounded-lg flex items-center justify-center text-blue-400 text-sm sm:text-lg border border-blue-800/40 shrink-0">
                            <i class="fas fa-university"></i>
                        </div>
                    </div>
                    <p class="text-[10px] sm:text-[11px] text-gray-400 mt-2 truncate">7 Branches &bull; 28 Sec</p>
                </div>
                
                <!-- 2. Registered Biometrics -->
                <div class="bg-cardbg rounded-xl p-3 sm:p-5 border border-gray-700/80 shadow-sm flex flex-col justify-between">
                    <div class="flex items-start justify-between gap-1">
                        <div class="min-w-0">
                            <p class="text-[10px] sm:text-xs font-semibold text-gray-400 uppercase tracking-wider truncate mb-0.5 sm:mb-1">Biometrics</p>
                            <h3 class="text-xl sm:text-2xl font-bold text-emerald-400 font-mono leading-none">${stats.registeredBiometrics}</h3>
                        </div>
                        <div class="w-8 h-8 sm:w-11 sm:h-11 bg-emerald-950/40 rounded-lg flex items-center justify-center text-emerald-400 text-sm sm:text-lg border border-emerald-800/50 shrink-0">
                            <i class="fas fa-id-card"></i>
                        </div>
                    </div>
                    <p class="text-[10px] sm:text-[11px] text-emerald-400 mt-2 truncate font-medium">128-d Vector Encrypted</p>
                </div>

                <!-- 3. Present Today -->
                <div class="bg-cardbg rounded-xl p-3 sm:p-5 border border-gray-700/80 shadow-sm flex flex-col justify-between">
                    <div class="flex items-start justify-between gap-1">
                        <div class="min-w-0">
                            <p class="text-[10px] sm:text-xs font-semibold text-gray-400 uppercase tracking-wider truncate mb-0.5 sm:mb-1">Present Today</p>
                            <h3 class="text-xl sm:text-2xl font-bold text-white font-mono leading-none">${stats.presentToday}</h3>
                        </div>
                        <div class="w-8 h-8 sm:w-11 sm:h-11 bg-blue-950/40 rounded-lg flex items-center justify-center text-blue-400 text-sm sm:text-lg border border-blue-800/50 shrink-0">
                            <i class="fas fa-check-double"></i>
                        </div>
                    </div>
                    <p class="text-[10px] sm:text-[11px] text-blue-400 mt-2 truncate font-medium">Verified BLE+Face</p>
                </div>

                <!-- 4. Active Lecture -->
                <div class="bg-cardbg rounded-xl p-3 sm:p-5 border border-gray-700/80 shadow-sm flex flex-col justify-between">
                    <div class="flex items-start justify-between gap-1">
                        <div class="min-w-0">
                            <p class="text-[10px] sm:text-xs font-semibold text-gray-400 uppercase tracking-wider truncate mb-0.5 sm:mb-1">Live Lecture</p>
                            <h3 class="text-xs sm:text-sm font-bold text-white truncate leading-tight mt-0.5" title="${activeSub}">${activeSub}</h3>
                        </div>
                        <div class="w-8 h-8 sm:w-11 sm:h-11 ${isWindowOpen ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50' : 'bg-slate-800 text-gray-400 border-slate-700'} rounded-lg flex items-center justify-center text-sm sm:text-lg border shrink-0">
                            <i class="fas ${isWindowOpen ? 'fa-door-open' : 'fa-clock'}"></i>
                        </div>
                    </div>
                    <p class="text-[10px] sm:text-[11px] font-semibold mt-2 truncate ${isWindowOpen ? 'text-emerald-400' : 'text-gray-400'}">
                        ${isWindowOpen ? '&bull; Window Active' : isClassActive ? '&bull; Window Closed' : 'No Active Session'}
                    </p>
                </div>
            </div>

            <!-- Recent Activity Table & Mobile Cards -->
            <div class="bg-cardbg rounded-xl border border-gray-700/80 overflow-hidden shadow-sm">
                <div class="px-3.5 py-3 sm:px-5 sm:py-3.5 border-b border-gray-700/80 flex justify-between items-center bg-slate-900/60">
                    <h3 class="text-xs sm:text-sm font-semibold text-white flex items-center gap-2">
                        <i class="fas fa-history text-blue-400"></i> Recent Attendance Logs
                    </h3>
                    <a href="#attendance" class="text-[11px] sm:text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 transition-colors">
                        View All <i class="fas fa-arrow-right"></i>
                    </a>
                </div>

                <!-- Mobile Card List View (Visible only on screens < 768px) -->
                <div class="block md:hidden divide-y divide-gray-700/50 p-2 sm:p-3">
                    ${recent.length > 0 ? recent.map(r => `
                        <div class="p-3 bg-slate-900/50 hover:bg-slate-800/60 rounded-lg my-1.5 border border-gray-700/40 transition-colors">
                            <div class="flex items-start justify-between gap-2 mb-1.5">
                                <div class="flex items-center gap-2.5 min-w-0">
                                    <div class="w-8 h-8 rounded-full bg-blue-900/40 text-blue-300 border border-blue-700/40 flex items-center justify-center font-bold text-xs shrink-0">
                                        ${r.name ? r.name.charAt(0).toUpperCase() : 'S'}
                                    </div>
                                    <div class="min-w-0">
                                        <div class="text-xs font-bold text-white truncate">${r.name || 'Student'}</div>
                                        <div class="text-[10px] text-gray-400 font-mono">${r.roll_no}</div>
                                    </div>
                                </div>
                                <span class="badge ${r.status === 'Present' ? 'badge-present' : 'badge-absent'} shrink-0">${r.status || 'Present'}</span>
                            </div>
                            <div class="flex items-center justify-between text-[11px] text-gray-300 pt-1.5 border-t border-gray-800/80 gap-2">
                                <div class="flex items-center gap-1.5 truncate">
                                    <span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-medium border border-slate-700 truncate max-w-[130px]">${r.subject || 'General'}</span>
                                    ${r.section ? `<span class="px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300 text-[10px] font-bold border border-blue-700/50">${r.section}</span>` : ''}
                                </div>
                                <span class="text-[10px] font-mono text-gray-400 shrink-0">${r.time || ''}</span>
                            </div>
                        </div>
                    `).join('') : `
                        <div class="py-8 text-center text-gray-400 text-xs">No attendance entries recorded today.</div>
                    `}
                </div>

                <!-- Desktop Table View (Visible only on tablets & desktops >= 768px) -->
                <div class="hidden md:block overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="text-gray-400 text-[11px] uppercase bg-cardbg border-b border-gray-700/80 font-semibold tracking-wider">
                                <th class="py-2.5 px-4 font-semibold">Date & Time</th>
                                <th class="py-2.5 px-4 font-semibold">Branch & Section</th>
                                <th class="py-2.5 px-4 font-semibold">Subject</th>
                                <th class="py-2.5 px-4 font-semibold">Student Name</th>
                                <th class="py-2.5 px-4 font-semibold">Roll Number</th>
                                <th class="py-2.5 px-4 font-semibold">Status</th>
                            </tr>
                        </thead>
                        <tbody class="text-xs divide-y divide-gray-700/40">
                            ${recent.length > 0 ? recent.map(r => `
                                <tr class="hover:bg-slate-800/50 transition-colors">
                                    <td class="py-2.5 px-4 text-gray-300 font-mono text-[11px]">
                                        <span class="text-white">${r.date}</span> <span class="text-gray-400">${r.time}</span>
                                    </td>
                                    <td class="py-2.5 px-4">
                                        <div class="flex items-center gap-1.5">
                                            ${r.branch_code ? `<span class="px-1.5 py-0.5 rounded bg-slate-700 text-slate-200 border border-slate-600 text-[10px] font-semibold">${r.branch_code}</span>` : ''}
                                            ${r.section ? `<span class="px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-700/50 font-mono text-[10px] font-bold">${r.section}</span>` : '<span class="text-gray-500">-</span>'}
                                        </div>
                                    </td>
                                    <td class="py-2.5 px-4">
                                        <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[11px] font-medium">${r.subject || 'General'}</span>
                                    </td>
                                    <td class="py-2.5 px-4 text-white font-medium">${r.name || '-'}</td>
                                    <td class="py-2.5 px-4 text-gray-300 font-mono text-[11px]">${r.roll_no}</td>
                                    <td class="py-2.5 px-4">
                                        <span class="badge ${r.status === 'Present' ? 'badge-present' : 'badge-absent'}">${r.status || 'Present'}</span>
                                    </td>
                                </tr>
                            `).join('') : `
                                <tr>
                                    <td colspan="6" class="py-8 text-center text-gray-400 text-xs">No attendance entries recorded today.</td>
                                </tr>
                            `}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        document.getElementById('refresh-dashboard').addEventListener('click', () => {
            this.render(container);
        });

        // Auto refresh setup
        const interval = setInterval(() => this.render(container), 20000);
        if (window.currentIntervals) window.currentIntervals.push(interval);
    }
};
