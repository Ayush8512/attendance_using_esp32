import { renderNavbar } from './components/navbar.js';
import dashboardPage from './pages/dashboard.js';
import studentsPage from './pages/students.js';
import attendancePage from './pages/attendance.js';
import classroomPage from './pages/classroom.js?v=1.2';
import timetablePage from './pages/timetable.js';

const routes = {
    '#dashboard': dashboardPage,
    '#timetable': timetablePage,
    '#students': studentsPage,
    '#attendance': attendancePage,
    '#classroom': classroomPage
};

function router() {
    let hash = window.location.hash || '#dashboard';
    if (!window.location.hash) {
        history.replaceState(null, '', '#dashboard');
    }

    const [path, query] = hash.split('?');
    if (path === '#register') {
        window.location.hash = '#students';
        return;
    }
    const page = routes[path] || routes['#dashboard'];
    
    const appDiv = document.getElementById('app');
    if (!appDiv) return;
    
    if (window.currentIntervals) {
        window.currentIntervals.forEach(clearInterval);
    }
    window.currentIntervals = [];

    appDiv.innerHTML = '<div class="flex items-center justify-center h-full"><div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-highlight"></div></div>';
    
    (async () => {
        try {
            await page.render(appDiv, query);
            renderNavbar(path);
        } catch (error) {
            console.error(error);
            appDiv.innerHTML = `<div class="text-red-500 p-4 bg-red-500 bg-opacity-20 rounded-lg">Error loading page: ${error.message}</div>`;
        }
    })();
}

document.addEventListener('DOMContentLoaded', () => {
    renderNavbar(window.location.hash || '#dashboard');
    window.addEventListener('hashchange', router);
    router();
});


window.handleLogout = async () => {
    if(confirm("Are you sure you want to log out?")) {
        await fetch('/api/auth/logout', {method: 'POST'});
        window.location.href = '/login.html';
    }
};
