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
            <div class="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4 border-b border-gray-700/60 pb-5">
                <div>
                    <h2 class="text-2xl font-bold text-white tracking-tight">Attendance Summary & Live Monitor</h2>
                    <p class="text-gray-400 text-sm mt-0.5">Institute of Engineering and Rural Technology, Prayagraj &bull; ${dateStr}</p>
                </div>
                <button id="refresh-dashboard" class="bg-cardbg border border-gray-600 hover:border-blue-500 text-gray-200 hover:text-white px-3.5 py-2 rounded-md transition-colors flex items-center gap-2 text-xs font-semibold shadow-sm">
                    <i class="fas fa-sync-alt"></i> Refresh Data
                </button>
            </div>

            <!-- Stats Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <!-- 1. Enrolled Roster -->
                <div class="bg-cardbg rounded-lg p-5 border border-gray-700/80 shadow-sm">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Enrolled Students</p>
                            <h3 class="text-2xl font-bold text-white font-mono">${stats.totalEnrolled.toLocaleString()}</h3>
                            <p class="text-[11px] text-gray-400 mt-1">7 Branches &bull; 28 Sections</p>
                        </div>
                        <div class="w-11 h-11 bg-blue-900/30 rounded-md flex items-center justify-center text-blue-400 text-lg border border-blue-800/40">
                            <i class="fas fa-university"></i>
                        </div>
                    </div>
                </div>
                
                <!-- 2. Registered Biometrics -->
                <div class="bg-cardbg rounded-lg p-5 border border-gray-700/80 shadow-sm">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Biometrics Active</p>
                            <h3 class="text-2xl font-bold text-emerald-400 font-mono">${stats.registeredBiometrics}</h3>
                            <p class="text-[11px] text-gray-400 mt-1">128-d Vector Encrypted</p>
                        </div>
                        <div class="w-11 h-11 bg-emerald-950/40 rounded-md flex items-center justify-center text-emerald-400 text-lg border border-emerald-800/50">
                            <i class="fas fa-id-card"></i>
                        </div>
                    </div>
                </div>

                <!-- 3. Present Today -->
                <div class="bg-cardbg rounded-lg p-5 border border-gray-700/80 shadow-sm">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Present Today</p>
                            <h3 class="text-2xl font-bold text-white font-mono">${stats.presentToday}</h3>
                            <p class="text-[11px] text-gray-400 mt-1">Verified Classroom Scans</p>
                        </div>
                        <div class="w-11 h-11 bg-blue-950/40 rounded-md flex items-center justify-center text-blue-400 text-lg border border-blue-800/50">
                            <i class="fas fa-check-double"></i>
                        </div>
                    </div>
                </div>

                <!-- 4. Active Lecture -->
                <div class="bg-cardbg rounded-lg p-5 border border-gray-700/80 shadow-sm">
                    <div class="flex items-center justify-between">
                        <div class="overflow-hidden mr-2">
                            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Current Lecture</p>
                            <h3 class="text-sm font-bold text-white truncate" title="${activeSub}">${activeSub}</h3>
                            <p class="text-[11px] font-semibold mt-1 ${isWindowOpen ? 'text-emerald-400' : 'text-gray-400'}">
                                ${isWindowOpen ? '&bull; Window Active (10 min)' : isClassActive ? '&bull; Window Closed' : 'No Active Session'}
                            </p>
                        </div>
                        <div class="w-11 h-11 ${isWindowOpen ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50' : 'bg-slate-800 text-gray-400 border-slate-700'} rounded-md flex items-center justify-center text-lg border shrink-0">
                            <i class="fas ${isWindowOpen ? 'fa-door-open' : 'fa-clock'}"></i>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Recent Activity Table -->
            <div class="bg-cardbg rounded-lg border border-gray-700/80 overflow-hidden shadow-sm">
                <div class="px-5 py-3.5 border-b border-gray-700/80 flex justify-between items-center bg-slate-900/60">
                    <h3 class="text-sm font-semibold text-white flex items-center gap-2">
                        <i class="fas fa-history text-blue-400"></i> Recent Classroom Attendance Logs
                    </h3>
                    <a href="#attendance" class="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 transition-colors">
                        View Complete Register <i class="fas fa-arrow-right"></i>
                    </a>
                </div>
                <div class="overflow-x-auto">
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
