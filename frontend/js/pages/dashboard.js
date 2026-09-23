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

            if (rosterStatsRes.status === 'fulfilled' && rosterStatsRes.value?.total_students) {
                stats.totalEnrolled = rosterStatsRes.value.total_students;
                stats.registeredBiometrics = rosterStatsRes.value.registered_count || 0;
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
            <div class="mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white mb-1">Campus Attendance Overview</h2>
                    <p class="text-gray-400 text-sm">${dateStr} • IERT Prayagraj Smart System</p>
                </div>
                <button id="refresh-dashboard" class="bg-cardbg border border-gray-600 hover:border-highlight text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2 text-sm">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
            </div>

            <!-- Stats Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
                <!-- 1. Enrolled Roster -->
                <div class="bg-cardbg rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-all shadow-md">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-medium text-gray-400 mb-1">College Enrolled Roster</p>
                            <h3 class="text-2xl font-bold text-white">${stats.totalEnrolled.toLocaleString()}</h3>
                            <p class="text-[11px] text-gray-400 mt-1">7 Branches • 28 Sections</p>
                        </div>
                        <div class="w-12 h-12 bg-accent/30 rounded-xl flex items-center justify-center text-highlight text-xl border border-highlight/20">
                            <i class="fas fa-graduation-cap"></i>
                        </div>
                    </div>
                </div>
                
                <!-- 2. Registered Biometrics -->
                <div class="bg-cardbg rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-all shadow-md">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-medium text-gray-400 mb-1">Biometrics Registered</p>
                            <h3 class="text-2xl font-bold text-green-400">${stats.registeredBiometrics}</h3>
                            <p class="text-[11px] text-gray-400 mt-1">Face models encrypted</p>
                        </div>
                        <div class="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center text-green-400 text-xl border border-green-500/30">
                            <i class="fas fa-fingerprint"></i>
                        </div>
                    </div>
                </div>

                <!-- 3. Present Today -->
                <div class="bg-cardbg rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-all shadow-md">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-medium text-gray-400 mb-1">Present Today</p>
                            <h3 class="text-2xl font-bold text-white">${stats.presentToday}</h3>
                            <p class="text-[11px] text-gray-400 mt-1">Unique verified scans</p>
                        </div>
                        <div class="w-12 h-12 bg-blue-500/20 rounded-xl flex items-center justify-center text-blue-400 text-xl border border-blue-500/30">
                            <i class="fas fa-user-check"></i>
                        </div>
                    </div>
                </div>

                <!-- 4. Active Lecture -->
                <div class="bg-cardbg rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-all shadow-md">
                    <div class="flex items-center justify-between">
                        <div class="overflow-hidden mr-2">
                            <p class="text-xs font-medium text-gray-400 mb-1">Current Lecture Window</p>
                            <h3 class="text-base font-bold text-white truncate" title="${activeSub}">${activeSub}</h3>
                            <p class="text-[11px] font-semibold mt-1 ${isWindowOpen ? 'text-green-400' : 'text-gray-400'}">
                                ${isWindowOpen ? '● Window Open (10 min)' : isClassActive ? '● Window Closed' : 'No Class'}
                            </p>
                        </div>
                        <div class="w-12 h-12 ${isWindowOpen ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-gray-700/50 text-gray-400 border-gray-600'} rounded-xl flex items-center justify-center text-xl border shrink-0">
                            <i class="fas ${isWindowOpen ? 'fa-door-open' : 'fa-clock'}"></i>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Recent Activity Table -->
            <div class="bg-cardbg rounded-xl border border-gray-700 overflow-hidden shadow-lg">
                <div class="px-6 py-4 border-b border-gray-700 flex justify-between items-center bg-gray-800 bg-opacity-50">
                    <h3 class="text-base font-semibold text-white flex items-center gap-2">
                        <i class="fas fa-history text-highlight"></i> Recent Live Attendance Logs
                    </h3>
                    <a href="#attendance" class="text-xs text-highlight hover:underline flex items-center gap-1">
                        View All Records <i class="fas fa-arrow-right"></i>
                    </a>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="text-gray-400 text-xs uppercase bg-cardbg border-b border-gray-700">
                                <th class="py-3 px-5 font-medium">Date & Time</th>
                                <th class="py-3 px-5 font-medium">Branch / Section</th>
                                <th class="py-3 px-5 font-medium">Subject</th>
                                <th class="py-3 px-5 font-medium">Student Name</th>
                                <th class="py-3 px-5 font-medium">Roll No</th>
                                <th class="py-3 px-5 font-medium">Status</th>
                            </tr>
                        </thead>
                        <tbody class="text-xs divide-y divide-gray-700/50">
                            ${recent.length > 0 ? recent.map(r => `
                                <tr class="hover:bg-gray-800 transition-colors">
                                    <td class="py-3 px-5 text-gray-300 font-mono">
                                        <span class="font-semibold text-white">${r.date}</span> <span class="text-gray-400">${r.time}</span>
                                    </td>
                                    <td class="py-3 px-5">
                                        <div class="flex items-center gap-1">
                                            ${r.branch_code ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold">${r.branch_code}</span>` : ''}
                                            ${r.section ? `<span class="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono text-[10px] font-bold">${r.section}</span>` : '<span class="text-gray-500">-</span>'}
                                        </div>
                                    </td>
                                    <td class="py-3 px-5">
                                        <span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[11px] font-medium">${r.subject || 'General'}</span>
                                    </td>
                                    <td class="py-3 px-5 text-white font-medium">${r.name || '-'}</td>
                                    <td class="py-3 px-5 text-gray-300 font-mono">${r.roll_no}</td>
                                    <td class="py-3 px-5">
                                        <span class="badge ${r.status === 'Present' ? 'badge-present' : 'badge-absent'}">${r.status || 'Present'}</span>
                                    </td>
                                </tr>
                            `).join('') : `
                                <tr>
                                    <td colspan="6" class="py-8 text-center text-gray-500">No attendance activity recorded yet today.</td>
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
