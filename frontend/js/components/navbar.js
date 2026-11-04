export function renderNavbar(currentPath) {
    const container = document.getElementById('navbar-container');
    if (!container) return;
    
    // Retrieve logged in user from localStorage if available
    let storedUser = null;
    try {
        const rawUser = localStorage.getItem('currentUser');
        if (rawUser) storedUser = JSON.parse(rawUser);
    } catch (_) {}

    const userName = storedUser ? storedUser.name : 'Faculty User';
    const userRole = storedUser ? (storedUser.role === 'admin' ? 'Administrator' : 'Teacher') : 'Teacher';
    const userDept = storedUser ? (storedUser.department || 'Faculty') : 'Faculty';
    const isAdmin = storedUser && storedUser.role === 'admin';

    const navItems = [
        { path: '#dashboard', icon: 'fa-chart-line', label: 'Dashboard', shortLabel: 'Overview' },
        { path: '#classroom', icon: 'fa-chalkboard-user', label: 'Classroom Live', shortLabel: 'Live Class' },
        { path: '#attendance', icon: 'fa-calendar-check', label: 'Attendance Records', shortLabel: 'Register' },
        { path: '#timetable', icon: 'fa-clock', label: 'Timetable & Windows', shortLabel: 'Timetable' },
        { path: '#students', icon: 'fa-users', label: 'Students List', shortLabel: 'Students' }
    ];

    if (isAdmin) {
        navItems.push({ path: '#teachers', icon: 'fa-user-tie', label: 'Teacher Management', shortLabel: 'Teachers' });
    }

    let navHtml = `
    <!-- Mobile Sidebar overlay -->
    <div id="sidebar-overlay" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 hidden md:hidden transition-opacity"></div>
    
    <!-- Sidebar for Desktop & Mobile Slideout Drawer -->
    <aside id="sidebar" class="fixed md:static inset-y-0 left-0 z-50 w-72 max-w-[85vw] md:w-64 bg-cardbg transform -translate-x-full md:translate-x-0 transition-transform duration-300 ease-in-out border-r border-gray-700/80 flex flex-col h-full shadow-2xl md:shadow-none">
        <div class="flex items-center justify-between px-5 h-16 md:h-20 border-b border-gray-700/80 gap-3">
            <div class="flex items-center gap-3 overflow-hidden">
                <div class="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-base shadow-sm shrink-0">
                    <i class="fas fa-university"></i>
                </div>
                <div class="leading-tight overflow-hidden">
                    <h1 class="text-sm font-bold text-white tracking-wide truncate">IERT PRAYAGRAJ</h1>
                    <p class="text-[11px] text-gray-400 font-mono">Attendance Portal</p>
                </div>
            </div>
            <!-- Close button on mobile drawer -->
            <button id="sidebar-close-btn" class="md:hidden text-gray-400 hover:text-white p-1.5 rounded-lg focus:outline-none">
                <i class="fas fa-times text-lg"></i>
            </button>
        </div>

        <!-- Logged In User Card -->
        <div class="px-4 py-3.5 border-b border-gray-700/80 bg-slate-900/60">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-full bg-blue-900/40 text-blue-400 border border-blue-800/40 flex items-center justify-center text-sm font-bold shrink-0">
                    <i class="fas ${isAdmin ? 'fa-user-shield' : 'fa-user-tie'}"></i>
                </div>
                <div class="overflow-hidden leading-tight min-w-0">
                    <div class="text-xs font-bold text-white truncate">${userName}</div>
                    <div class="text-[10px] text-gray-400 font-medium flex items-center gap-1 mt-0.5">
                        <span class="px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-700/50 font-semibold">${userRole}</span>
                        <span class="text-gray-400 truncate">&bull; ${userDept}</span>
                    </div>
                </div>
            </div>
        </div>

        <nav class="flex-1 px-3 py-3 space-y-1 overflow-y-auto">
    `;

    navItems.forEach(item => {
        const isActive = currentPath === item.path;
        const baseClass = "flex items-center px-3.5 py-2.5 rounded-lg transition-all text-sm font-medium touch-manipulation";
        const activeClass = isActive 
            ? "bg-blue-600 text-white shadow-sm font-semibold" 
            : "text-gray-300 hover:bg-slate-800 hover:text-white";
            
        navHtml += `
            <a href="${item.path}" class="${baseClass} ${activeClass}">
                <i class="fas ${item.icon} w-5 text-center mr-3 ${isActive ? 'text-white' : 'text-gray-400'}"></i>
                <span>${item.label}</span>
            </a>
        `;
    });

    navHtml += `
        </nav>
        <div class="p-3.5 border-t border-gray-700/80 bg-slate-900/30">
            <div class="flex items-center justify-between text-xs text-gray-400 font-mono">
                <span class="flex items-center gap-1.5"><i class="fas fa-broadcast-tower text-blue-400 text-[11px]"></i> BLE Beacon</span>
                <span class="flex h-2.5 w-2.5 relative">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </span>
            </div>
        </div>
    
        <div class="p-3.5 border-t border-gray-700/80">
            <button onclick="window.handleLogout()" class="w-full flex items-center justify-center gap-2.5 px-3 py-2 text-red-400 hover:text-white hover:bg-red-600/90 rounded-lg transition-colors text-xs font-semibold border border-red-500/30 active:scale-98">
                <i class="fas fa-sign-out-alt"></i>
                <span>Logout Faculty</span>
            </button>
        </div>
    </aside>

    <!-- Mobile Bottom Navigation Bar (Thumb Friendly) -->
    <nav id="mobile-bottom-nav" class="md:hidden fixed bottom-0 left-0 right-0 bg-cardbg/95 backdrop-blur-md border-t border-gray-700/80 z-30 px-2 py-1.5 flex items-center justify-around shadow-2xl pb-[max(0.4rem,env(safe-area-inset-bottom))]">
        <a href="#dashboard" class="mobile-nav-link flex flex-col items-center py-1 px-2.5 rounded-lg transition-colors ${currentPath === '#dashboard' ? 'mobile-nav-active font-bold' : 'text-gray-400'}">
            <i class="fas fa-chart-line text-base"></i>
            <span class="text-[10px] font-medium mt-0.5">Overview</span>
        </a>
        <a href="#classroom" class="mobile-nav-link flex flex-col items-center py-1 px-2.5 rounded-lg transition-colors ${currentPath === '#classroom' ? 'mobile-nav-active font-bold' : 'text-gray-400'}">
            <i class="fas fa-chalkboard-user text-base"></i>
            <span class="text-[10px] font-medium mt-0.5">Live Class</span>
        </a>
        <a href="#attendance" class="mobile-nav-link flex flex-col items-center py-1 px-2.5 rounded-lg transition-colors ${currentPath === '#attendance' ? 'mobile-nav-active font-bold' : 'text-gray-400'}">
            <i class="fas fa-calendar-check text-base"></i>
            <span class="text-[10px] font-medium mt-0.5">Register</span>
        </a>
        <a href="#timetable" class="mobile-nav-link flex flex-col items-center py-1 px-2.5 rounded-lg transition-colors ${currentPath === '#timetable' ? 'mobile-nav-active font-bold' : 'text-gray-400'}">
            <i class="fas fa-clock text-base"></i>
            <span class="text-[10px] font-medium mt-0.5">Timetable</span>
        </a>
        <a href="#students" class="mobile-nav-link flex flex-col items-center py-1 px-2.5 rounded-lg transition-colors ${currentPath === '#students' ? 'mobile-nav-active font-bold' : 'text-gray-400'}">
            <i class="fas fa-users text-base"></i>
            <span class="text-[10px] font-medium mt-0.5">Students</span>
        </a>
    </nav>
    `;

    container.innerHTML = navHtml;

    // Mobile menu toggle logic
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const closeBtn = document.getElementById('sidebar-close-btn');

    if (sidebar && overlay) {
        const openSidebar = () => {
            sidebar.classList.remove('-translate-x-full');
            overlay.classList.remove('hidden');
            document.body.classList.add('overflow-hidden');
        };

        const closeSidebar = () => {
            sidebar.classList.add('-translate-x-full');
            overlay.classList.add('hidden');
            document.body.classList.remove('overflow-hidden');
        };

        if (mobileBtn) {
            const newBtn = mobileBtn.cloneNode(true);
            mobileBtn.parentNode.replaceChild(newBtn, mobileBtn);
            newBtn.addEventListener('click', openSidebar);
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', closeSidebar);
        }

        overlay.addEventListener('click', closeSidebar);
        
        sidebar.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 768) {
                    closeSidebar();
                }
            });
        });
    }
}
