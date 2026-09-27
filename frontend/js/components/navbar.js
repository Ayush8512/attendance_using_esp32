export function renderNavbar(currentPath) {
    const container = document.getElementById('navbar-container');
    
    const navItems = [
        { path: '#dashboard', icon: 'fa-chart-line', label: 'Dashboard' },
        { path: '#timetable', icon: 'fa-clock', label: 'Timetable & Windows' },
        { path: '#students', icon: 'fa-users', label: 'Students List' },
        { path: '#attendance', icon: 'fa-calendar-check', label: 'Attendance Records' },
        { path: '#classroom', icon: 'fa-chalkboard-user', label: 'Classroom Live' }
    ];

    let navHtml = `
    <!-- Mobile Sidebar overlay -->
    <div id="sidebar-overlay" class="fixed inset-0 bg-black bg-opacity-50 z-20 hidden md:hidden"></div>
    
    <!-- Sidebar -->
    <aside id="sidebar" class="fixed md:static inset-y-0 left-0 z-30 w-64 bg-cardbg transform -translate-x-full md:translate-x-0 transition-transform duration-300 ease-in-out border-r border-gray-700 flex flex-col h-full">
        <div class="flex items-center px-5 h-20 border-b border-gray-700/80 gap-3">
            <div class="w-9 h-9 rounded-md bg-blue-600 flex items-center justify-center text-white font-bold text-base shadow-sm shrink-0">
                <i class="fas fa-university"></i>
            </div>
            <div class="leading-tight overflow-hidden">
                <h1 class="text-sm font-bold text-white tracking-wide truncate">IERT PRAYAGRAJ</h1>
                <p class="text-[11px] text-gray-400 font-mono">Attendance Portal</p>
            </div>
        </div>
        <nav class="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
    `;

    navItems.forEach(item => {
        const isActive = currentPath === item.path;
        const baseClass = "flex items-center px-3.5 py-2.5 rounded-md transition-colors text-sm font-medium";
        const activeClass = isActive 
            ? "bg-blue-600 text-white shadow-sm" 
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
        <div class="p-4 border-t border-gray-700">
            <div class="flex items-center justify-between text-sm text-gray-400">
                <span>System Status</span>
                <span class="flex h-3 w-3 relative">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                </span>
            </div>
        </div>
    
    <div class="p-4 mt-auto border-t border-gray-700">
        <button onclick="window.handleLogout()" class="w-full flex items-center gap-3 px-4 py-3 text-red-400 hover:text-white hover:bg-red-600 rounded-lg transition-colors">
            <i class="fas fa-sign-out-alt"></i>
            <span class="font-medium">Logout</span>
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
