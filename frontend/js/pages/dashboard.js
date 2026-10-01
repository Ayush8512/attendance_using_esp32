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
            health: 'Online' 
        };
        let recent = [];
        let branchCounts = { A: 0, B: 0, C: 0, D: 0, E: 0, F: 0, G: 0 };
        let branchPresent = { A: 0, B: 0, C: 0, D: 0, E: 0, F: 0, G: 0 };

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

                    // Branch breakdown calculation
                    todayRecords.forEach(r => {
                        const code = (r.branch_code || (r.roll_no ? r.roll_no[0] : '')).toUpperCase();
                        if (branchPresent.hasOwnProperty(code)) {
                            branchPresent[code]++;
                        }
                    });
                }
            }
        } catch (e) {
            console.error("Error fetching stats", e);
        }

        const isClassActive = !!stats.activeClass?.class;
        const activeSub = isClassActive ? stats.activeClass.class.subject : 'No Active Session';
        const activeSec = isClassActive ? (stats.activeClass.class.section || 'All Sections') : 'N/A';
        const isWindowOpen = isClassActive && stats.activeClass.window_status?.is_open;
        const windowEnd = isClassActive ? (stats.activeClass.window_status?.window_end || 'N/A') : 'N/A';

        const bioPercent = Math.min(100, Math.round((stats.registeredBiometrics / (stats.totalEnrolled || 1)) * 100));
        const presentPercent = Math.min(100, Math.round((stats.presentToday / (stats.registeredBiometrics || 1)) * 100));

        // Define the 4 modular draggable widgets
        const widgetTemplates = {
            'stats-cards': `
                <div class="draggable-widget perspective-container mb-6" data-widget-id="stats-cards" draggable="true">
                    <div class="flex items-center justify-between mb-3 text-xs text-gray-400 font-semibold uppercase tracking-wider px-1">
                        <span class="flex items-center gap-2"><i class="fas fa-grip-vertical text-blue-400 drag-handle"></i> Core Performance Indicators</span>
                        <span class="text-[10px] text-blue-400/80 font-mono">Draggable Widget</span>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <!-- Card 1: Total Enrolled -->
                        <div class="glass-panel glass-panel-glow tilt-card rounded-xl p-5 border border-white/10 shadow-xl">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Enrolled Roster</p>
                                    <h3 class="text-3xl font-bold text-white font-mono tracking-tight">${stats.totalEnrolled.toLocaleString()}</h3>
                                    <p class="text-[11px] text-blue-400 mt-1 flex items-center gap-1 font-medium">
                                        <i class="fas fa-layer-group"></i> 7 Branches &bull; 28 Sections
                                    </p>
                                </div>
                                <div class="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center text-blue-400 text-xl border border-blue-500/30 shadow-inner">
                                    <i class="fas fa-university"></i>
                                </div>
                            </div>
                        </div>

                        <!-- Card 2: Biometrics Active -->
                        <div class="glass-panel glass-panel-glow tilt-card rounded-xl p-5 border border-white/10 shadow-xl">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Biometrics Active</p>
                                    <h3 class="text-3xl font-bold text-emerald-400 font-mono tracking-tight">${stats.registeredBiometrics}</h3>
                                    <div class="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden border border-slate-700">
                                        <div class="bg-gradient-to-r from-emerald-500 to-teal-300 h-full rounded-full" style="width: ${bioPercent}%"></div>
                                    </div>
                                    <p class="text-[10px] text-emerald-400/90 mt-1 font-mono">${bioPercent}% Roster Face Registered</p>
                                </div>
                                <div class="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center text-emerald-400 text-xl border border-emerald-500/30 shadow-inner">
                                    <i class="fas fa-fingerprint"></i>
                                </div>
                            </div>
                        </div>

                        <!-- Card 3: Present Today -->
                        <div class="glass-panel glass-panel-glow tilt-card rounded-xl p-5 border border-white/10 shadow-xl">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Present Today</p>
                                    <h3 class="text-3xl font-bold text-cyan-300 font-mono tracking-tight">${stats.presentToday}</h3>
                                    <div class="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden border border-slate-700">
                                        <div class="bg-gradient-to-r from-cyan-500 to-blue-400 h-full rounded-full" style="width: ${presentPercent}%"></div>
                                    </div>
                                    <p class="text-[10px] text-cyan-300/90 mt-1 font-mono">${presentPercent}% Scanned Attendance</p>
                                </div>
                                <div class="w-12 h-12 bg-cyan-500/10 rounded-xl flex items-center justify-center text-cyan-400 text-xl border border-cyan-500/30 shadow-inner">
                                    <i class="fas fa-user-check"></i>
                                </div>
                            </div>
                        </div>

                        <!-- Card 4: System Health & ESP32 -->
                        <div class="glass-panel glass-panel-glow tilt-card rounded-xl p-5 border border-white/10 shadow-xl">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1">ESP32 & Node Status</p>
                                    <h3 class="text-xl font-bold text-white flex items-center gap-2 mt-1">
                                        <span class="flex h-3 w-3 relative">
                                          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                          <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                                        </span>
                                        ${stats.health}
                                    </h3>
                                    <p class="text-[10px] text-emerald-400 mt-2 font-mono flex items-center gap-1">
                                        <i class="fas fa-wifi text-[9px]"></i> iBeacon BLE Active (-59 dBm)
                                    </p>
                                </div>
                                <div class="w-12 h-12 bg-purple-500/10 rounded-xl flex items-center justify-center text-purple-400 text-xl border border-purple-500/30 shadow-inner">
                                    <i class="fas fa-microchip"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `,

            'active-lecture': `
                <div class="draggable-widget mb-6" data-widget-id="active-lecture" draggable="true">
                    <div class="glass-panel rounded-xl p-6 border border-white/10 shadow-2xl relative overflow-hidden">
                        <div class="flex items-center justify-between border-b border-gray-700/60 pb-4 mb-4">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/40 flex items-center justify-center text-lg drag-handle">
                                    <i class="fas fa-chalkboard-teacher"></i>
                                </div>
                                <div>
                                    <h3 class="text-base font-bold text-white tracking-wide">Live Classroom & ESP32 Beacon Stream</h3>
                                    <p class="text-xs text-gray-400">Real-time attendance window monitor & classroom proximity beacon</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                ${isWindowOpen ? `
                                    <span class="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 animate-pulse">
                                        <span class="w-2 h-2 rounded-full bg-emerald-400"></span> Attendance Window OPEN
                                    </span>
                                ` : `
                                    <span class="px-3 py-1 rounded-full text-xs font-semibold bg-gray-800 text-gray-400 border border-gray-700">
                                        &bull; Idle / Closed Window
                                    </span>
                                `}
                            </div>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div class="bg-darkbg/70 rounded-lg p-4 border border-gray-800">
                                <span class="text-[11px] font-semibold text-gray-400 uppercase">Active Subject</span>
                                <h4 class="text-base font-bold text-white mt-1 truncate" title="${activeSub}">${activeSub}</h4>
                                <span class="text-xs text-blue-400 font-mono mt-1 block">Section: ${activeSec}</span>
                            </div>
                            <div class="bg-darkbg/70 rounded-lg p-4 border border-gray-800">
                                <span class="text-[11px] font-semibold text-gray-400 uppercase">Window Closes At</span>
                                <h4 class="text-base font-bold text-emerald-400 mt-1 font-mono">${windowEnd}</h4>
                                <span class="text-xs text-gray-400 mt-1 block">Strict 10-Minute Limit</span>
                            </div>
                            <div class="bg-darkbg/70 rounded-lg p-4 border border-gray-800 flex items-center justify-between">
                                <div>
                                    <span class="text-[11px] font-semibold text-gray-400 uppercase">Scanned Present</span>
                                    <h4 class="text-lg font-bold text-white mt-0.5 font-mono">${stats.presentToday} Students</h4>
                                </div>
                                <a href="#classroom" class="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-1">
                                    <span>Monitor</span> <i class="fas fa-chevron-right text-[10px]"></i>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            `,

            'branch-breakdown': `
                <div class="draggable-widget mb-6" data-widget-id="branch-breakdown" draggable="true">
                    <div class="glass-panel rounded-xl p-6 border border-white/10 shadow-2xl">
                        <div class="flex items-center justify-between mb-5 border-b border-gray-700/60 pb-3">
                            <h3 class="text-sm font-bold text-white flex items-center gap-2">
                                <i class="fas fa-grip-vertical text-blue-400 drag-handle"></i>
                                <i class="fas fa-chart-bar text-cyan-400"></i> Departmental Attendance Breakdown (7 Engineering Branches)
                            </h3>
                            <span class="text-xs text-gray-400 font-mono">Today's Scanned Distribution</span>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            <!-- CSE -->
                            <div class="bg-darkbg/60 rounded-lg p-3.5 border border-gray-800">
                                <div class="flex justify-between items-center mb-1.5 text-xs">
                                    <span class="font-bold text-white">A - CSE</span>
                                    <span class="font-mono text-cyan-400 font-bold">${branchPresent.A} Scanned</span>
                                </div>
                                <div class="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                                    <div class="bg-cyan-400 h-full rounded-full" style="width: ${Math.min(100, branchPresent.A * 12)}%"></div>
                                </div>
                                <span class="text-[10px] text-gray-400 mt-1 block">Computer Science & Eng.</span>
                            </div>

                            <!-- ECE -->
                            <div class="bg-darkbg/60 rounded-lg p-3.5 border border-gray-800">
                                <div class="flex justify-between items-center mb-1.5 text-xs">
                                    <span class="font-bold text-white">B - ECE</span>
                                    <span class="font-mono text-blue-400 font-bold">${branchPresent.B} Scanned</span>
                                </div>
                                <div class="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                                    <div class="bg-blue-400 h-full rounded-full" style="width: ${Math.min(100, branchPresent.B * 12)}%"></div>
                                </div>
                                <span class="text-[10px] text-gray-400 mt-1 block">Electronics Engineering</span>
                            </div>

                            <!-- ME -->
                            <div class="bg-darkbg/60 rounded-lg p-3.5 border border-gray-800">
                                <div class="flex justify-between items-center mb-1.5 text-xs">
                                    <span class="font-bold text-white">D - ME</span>
                                    <span class="font-mono text-purple-400 font-bold">${branchPresent.D} Scanned</span>
                                </div>
                                <div class="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                                    <div class="bg-purple-400 h-full rounded-full" style="width: ${Math.min(100, branchPresent.D * 12)}%"></div>
                                </div>
                                <span class="text-[10px] text-gray-400 mt-1 block">Mechanical Engineering</span>
                            </div>

                            <!-- EE -->
                            <div class="bg-darkbg/60 rounded-lg p-3.5 border border-gray-800">
                                <div class="flex justify-between items-center mb-1.5 text-xs">
                                    <span class="font-bold text-white">F - EE</span>
                                    <span class="font-mono text-emerald-400 font-bold">${branchPresent.F} Scanned</span>
                                </div>
                                <div class="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                                    <div class="bg-emerald-400 h-full rounded-full" style="width: ${Math.min(100, branchPresent.F * 12)}%"></div>
                                </div>
                                <span class="text-[10px] text-gray-400 mt-1 block">Electrical Engineering</span>
                            </div>
                        </div>
                    </div>
                </div>
            `,

            'recent-logs': `
                <div class="draggable-widget mb-6" data-widget-id="recent-logs" draggable="true">
                    <div class="glass-panel rounded-xl border border-white/10 overflow-hidden shadow-2xl">
                        <div class="px-5 py-4 border-b border-gray-700/80 flex justify-between items-center bg-slate-900/80">
                            <h3 class="text-sm font-bold text-white flex items-center gap-2">
                                <i class="fas fa-grip-vertical text-blue-400 drag-handle"></i>
                                <i class="fas fa-stream text-blue-400"></i> Real-Time Classroom Attendance Stream
                            </h3>
                            <a href="#attendance" class="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 transition-colors">
                                View Full Register <i class="fas fa-arrow-right"></i>
                            </a>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left border-collapse">
                                <thead>
                                    <tr class="text-gray-400 text-[11px] uppercase bg-slate-900/40 border-b border-gray-700/80 font-semibold tracking-wider">
                                        <th class="py-3 px-4 font-semibold">Date & Time</th>
                                        <th class="py-3 px-4 font-semibold">Branch & Section</th>
                                        <th class="py-3 px-4 font-semibold">Subject</th>
                                        <th class="py-3 px-4 font-semibold">Student Name</th>
                                        <th class="py-3 px-4 font-semibold">Roll Number</th>
                                        <th class="py-3 px-4 font-semibold">Status</th>
                                    </tr>
                                </thead>
                                <tbody class="text-xs divide-y divide-gray-700/40">
                                    ${recent.length > 0 ? recent.map(r => `
                                        <tr class="hover:bg-slate-800/60 transition-colors">
                                            <td class="py-3 px-4 text-gray-300 font-mono text-[11px]">
                                                <span class="text-white">${r.date}</span> <span class="text-gray-400">${r.time}</span>
                                            </td>
                                            <td class="py-3 px-4">
                                                <div class="flex items-center gap-1.5">
                                                    ${r.branch_code ? `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700 text-[10px] font-semibold">${r.branch_code}</span>` : ''}
                                                    ${r.section ? `<span class="px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-300 border border-blue-700/50 font-mono text-[10px] font-bold">${r.section}</span>` : '<span class="text-gray-500">-</span>'}
                                                </div>
                                            </td>
                                            <td class="py-3 px-4">
                                                <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[11px] font-medium">${r.subject || 'General'}</span>
                                            </td>
                                            <td class="py-3 px-4 text-white font-medium">${r.name || '-'}</td>
                                            <td class="py-3 px-4 text-gray-300 font-mono text-[11px]">${r.roll_no}</td>
                                            <td class="py-3 px-4">
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
                </div>
            `
        };

        // Saved layout order from localStorage or default
        const savedOrder = JSON.parse(localStorage.getItem('dashboard_widget_order') || '["stats-cards", "active-lecture", "branch-breakdown", "recent-logs"]');
        const orderedWidgetsHtml = savedOrder.map(id => widgetTemplates[id] || '').join('');

        container.innerHTML = `
            <!-- Top Dashboard Header & Ticker -->
            <div class="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4 border-b border-gray-700/60 pb-5">
                <div>
                    <h2 class="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
                        <i class="fas fa-atom text-cyan-400 animate-spin" style="animation-duration: 10s;"></i>
                        Antigravity Attendance Dashboard
                    </h2>
                    <p class="text-gray-400 text-sm mt-1">
                        Institute of Engineering and Rural Technology, Prayagraj &bull; <span class="text-blue-400 font-medium">${dateStr}</span>
                    </p>
                </div>
                
                <div class="flex items-center gap-3">
                    <button id="btn-reset-layout" class="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-gray-300 hover:text-white px-3.5 py-2 rounded-lg text-xs font-semibold transition-all">
                        <i class="fas fa-undo mr-1"></i> Reset Layout
                    </button>
                    <button id="refresh-dashboard" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-all flex items-center gap-2 text-xs font-semibold shadow-lg shadow-blue-600/30">
                        <i class="fas fa-sync-alt"></i> Refresh Stream
                    </button>
                </div>
            </div>

            <!-- Real-Time Live Ticker Bar -->
            <div class="glass-panel rounded-xl p-3 mb-6 border border-cyan-500/30 shadow-lg flex items-center gap-3 overflow-hidden bg-slate-900/80">
                <span class="px-2.5 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[11px] font-bold tracking-wider uppercase shrink-0 flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span> LIVE TICKER
                </span>
                <div class="ticker-wrap flex-1 text-xs text-gray-300 font-mono">
                    <div class="ticker-content">
                        <span>⚡ ESP32 iBeacon Classroom Scanner Active (-59 dBm)</span> &bull; 
                        <span>📊 Enrolled Roster: ${stats.totalEnrolled} Students</span> &bull; 
                        <span>👤 Registered Biometrics: ${stats.registeredBiometrics} Encodings</span> &bull; 
                        <span>✅ Present Today: ${stats.presentToday} Scans</span> &bull; 
                        <span>🎓 Active Session: ${activeSub} (${activeSec})</span> &bull;
                    </div>
                </div>
            </div>

            <!-- Draggable Widgets Container -->
            <div id="widgets-container">
                ${orderedWidgetsHtml}
            </div>
        `;

        // Initialize 3D Particle Canvas
        this.initParticleCanvas();

        // Initialize Card 3D Tilt Effects
        this.initCardTilt();

        // Initialize Drag and Drop Layout Handler
        this.initDragAndDrop(container);

        document.getElementById('refresh-dashboard').addEventListener('click', () => {
            this.render(container);
        });

        document.getElementById('btn-reset-layout').addEventListener('click', () => {
            localStorage.removeItem('dashboard_widget_order');
            this.render(container);
        });

        // Auto refresh stream every 20s
        const interval = setInterval(() => this.render(container), 20000);
        if (window.currentIntervals) window.currentIntervals.push(interval);
    },

    initParticleCanvas() {
        const canvas = document.getElementById('bg-particles-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;

        const particles = [];
        const numParticles = 45;
        let mouseX = width / 2;
        let mouseY = height / 2;

        window.addEventListener('resize', () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        });

        window.addEventListener('mousemove', (e) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
        });

        for (let i = 0; i < numParticles; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                radius: Math.random() * 2 + 1,
            });
        }

        function draw() {
            ctx.clearRect(0, 0, width, height);

            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];
                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0) p.x = width;
                if (p.x > width) p.x = 0;
                if (p.y < 0) p.y = height;
                if (p.y > height) p.y = 0;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(0, 242, 254, 0.4)';
                ctx.fill();

                for (let j = i + 1; j < particles.length; j++) {
                    const p2 = particles[j];
                    const dx = p.x - p2.x;
                    const dy = p.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 130) {
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.strokeStyle = `rgba(0, 242, 254, ${0.15 * (1 - dist / 130)})`;
                        ctx.lineWidth = 0.6;
                        ctx.stroke();
                    }
                }
            }
            requestAnimationFrame(draw);
        }
        draw();
    },

    initCardTilt() {
        const tiltCards = document.querySelectorAll('.tilt-card');
        tiltCards.forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                const rotateX = (-y / rect.height) * 10;
                const rotateY = (x / rect.width) * 10;
                card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
            });
        });
    },

    initDragAndDrop(container) {
        const widgetsContainer = document.getElementById('widgets-container');
        if (!widgetsContainer) return;

        let draggedItem = null;

        widgetsContainer.querySelectorAll('.draggable-widget').forEach(widget => {
            widget.addEventListener('dragstart', (e) => {
                draggedItem = widget;
                widget.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });

            widget.addEventListener('dragend', () => {
                widget.classList.remove('dragging');
                widgetsContainer.querySelectorAll('.draggable-widget').forEach(w => w.classList.remove('drag-over'));
                
                // Save new layout order
                const newOrder = Array.from(widgetsContainer.querySelectorAll('.draggable-widget')).map(w => w.getAttribute('data-widget-id'));
                localStorage.setItem('dashboard_widget_order', JSON.stringify(newOrder));
            });

            widget.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                widget.classList.add('drag-over');
            });

            widget.addEventListener('dragleave', () => {
                widget.classList.remove('drag-over');
            });

            widget.addEventListener('drop', (e) => {
                e.preventDefault();
                widget.classList.remove('drag-over');
                if (draggedItem && draggedItem !== widget) {
                    const allWidgets = Array.from(widgetsContainer.children);
                    const draggedIndex = allWidgets.indexOf(draggedItem);
                    const targetIndex = allWidgets.indexOf(widget);

                    if (draggedIndex < targetIndex) {
                        widgetsContainer.insertBefore(draggedItem, widget.nextSibling);
                    } else {
                        widgetsContainer.insertBefore(draggedItem, widget);
                    }
                }
            });
        });
    }
};
