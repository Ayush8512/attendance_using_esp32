export function renderNavbar(currentPath) {
    const container = document.getElementById('navbar-container');
    
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
        { path: '#dashboard', icon: 'fa-chart-line', label: 'Dashboard' },
        { path: '#timetable', icon: 'fa-clock', label: 'Timetable & Windows' },
        { path: '#students', icon: 'fa-users', label: 'Students List' },
        { path: '#attendance', icon: 'fa-calendar-check', label: 'Attendance Records' },
        { path: '#classroom', icon: 'fa-chalkboard-user', label: 'Classroom Live' }
    ];

    if (isAdmin) {
        navItems.push({ path: '#teachers', icon: 'fa-user-tie', label: 'Teacher Management' });
    }

    let navHtml = `
    <!-- Mobile Sidebar overlay -->
    <div id="sidebar-overlay" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-20 hidden md:hidden"></div>
    
    <!-- Sidebar -->
    <aside id="sidebar" class="fixed md:static inset-y-0 left-0 z-30 w-64 bg-white transform -translate-x-full md:translate-x-0 transition-transform duration-300 ease-in-out border-r border-slate-200 flex flex-col h-full shadow-sm">
        <div class="flex items-center px-5 h-20 border-b border-slate-200 gap-3">
            <div class="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-base shadow-sm shrink-0">
                <i class="fas fa-university"></i>
            </div>
            <div class="leading-tight overflow-hidden">
                <h1 class="text-sm font-bold text-slate-900 tracking-wide truncate">IERT PRAYAGRAJ</h1>
                <p class="text-[11px] text-slate-500 font-mono">Attendance Portal</p>
            </div>
        </div>

        <!-- Logged In User Card -->
        <div class="px-3.5 py-3 border-b border-slate-200 bg-slate-50/70">
            <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-700 border border-blue-200 flex items-center justify-center text-xs font-bold shrink-0">
                    <i class="fas ${isAdmin ? 'fa-user-shield' : 'fa-user-tie'}"></i>
                </div>
                <div class="overflow-hidden leading-tight">
                    <div class="text-xs font-semibold text-slate-900 truncate">${userName}</div>
                    <div class="text-[10px] text-blue-600 font-medium flex items-center gap-1 mt-0.5">
                        <span class="px-1.5 py-0.2 rounded ${isAdmin ? 'bg-purple-100 text-purple-700 border border-purple-200' : 'bg-blue-100 text-blue-700 border border-blue-200'}">${userRole}</span>
                        <span class="text-slate-500 truncate">• ${userDept}</span>
                    </div>
                </div>
            </div>
        </div>

        <nav class="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
    `;

    navItems.forEach(item => {
        const isActive = currentPath === item.path;
        const baseClass = "flex items-center px-3.5 py-2.5 rounded-lg transition-colors text-sm font-medium";
        const activeClass = isActive 
            ? "bg-blue-600 text-white shadow-sm" 
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900";
            
        navHtml += `
            <a href="${item.path}" class="${baseClass} ${activeClass}">
                <i class="fas ${item.icon} w-5 text-center mr-3 ${isActive ? 'text-white' : 'text-slate-400'}"></i>
                <span>${item.label}</span>
            </a>
        `;
    });

    navHtml += `
        </nav>
        <div class="p-4 border-t border-slate-200">
            <div class="flex items-center justify-between text-xs text-slate-600 font-medium">
                <span>System Status</span>
                <span class="flex h-3 w-3 relative">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
            </div>
        </div>
    
    <div class="p-4 mt-auto border-t border-slate-200">
        <button onclick="window.handleLogout()" class="w-full flex items-center gap-3 px-4 py-2.5 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors text-xs font-semibold">
            <i class="fas fa-sign-out-alt"></i>
            <span>Logout</span>
        </button>
    </div>
    </aside>
    `;

    container.innerHTML = navHtml;

    // Mobile menu logic
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (mobileBtn && sidebar && overlay) {
        const toggleSidebar = () => {
            sidebar.classList.toggle('-translate-x-full');
            overlay.classList.toggle('hidden');
        };

        const newBtn = mobileBtn.cloneNode(true);
        mobileBtn.parentNode.replaceChild(newBtn, mobileBtn);
        
        newBtn.addEventListener('click', toggleSidebar);
        overlay.addEventListener('click', toggleSidebar);
        
        sidebar.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 768) {
                    toggleSidebar();
                }
            });
        });
    }
}
