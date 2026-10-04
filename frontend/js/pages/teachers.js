import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export async function renderTeachersPage(container) {
    container.innerHTML = `
        <div class="flex items-center justify-between mb-6">
            <div>
                <h1 class="text-2xl font-bold text-white tracking-wide">👨‍🏫 Teacher Management</h1>
                <p class="text-sm text-gray-400 mt-1">Manage faculty accounts, teacher credentials, and department roles</p>
            </div>
            <button id="add-teacher-btn" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2.5 rounded-lg text-sm flex items-center gap-2 shadow-sm transition-colors">
                <i class="fas fa-plus"></i>
                <span>Add Teacher</span>
            </button>
        </div>

        <!-- Teachers Grid / Table Container -->
        <div class="bg-cardbg border border-gray-700/80 rounded-xl overflow-hidden shadow-lg">
            <div class="p-4 border-b border-gray-700 flex flex-col md:flex-row items-center justify-between gap-4">
                <div class="relative w-full md:w-72">
                    <i class="fas fa-search absolute left-3 top-3 text-gray-400 text-sm"></i>
                    <input type="text" id="teacher-search-input" placeholder="Search teacher by name or email..." class="w-full bg-darkbg border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500">
                </div>
                <div id="teacher-count-badge" class="text-xs font-mono text-gray-400">
                    Loading faculty directory...
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-800/60 text-gray-400 text-xs font-semibold uppercase tracking-wider border-b border-gray-700">
                            <th class="py-3.5 px-4">Faculty Member</th>
                            <th class="py-3.5 px-4">Email / Login ID</th>
                            <th class="py-3.5 px-4">Department</th>
                            <th class="py-3.5 px-4">Role</th>
                            <th class="py-3.5 px-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="teachers-table-body" class="divide-y divide-gray-700/60 text-sm text-gray-300">
                        <tr>
                            <td colspan="5" class="py-8 text-center text-gray-500">
                                <i class="fas fa-circle-notch fa-spin text-xl mb-2"></i>
                                <p>Loading teacher directory...</p>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Add Teacher Modal -->
        <div id="add-teacher-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
            <div class="bg-cardbg border border-gray-700 rounded-xl max-w-md w-full p-6 shadow-2xl relative">
                <div class="flex items-center justify-between border-b border-gray-700 pb-4 mb-4">
                    <h3 class="text-lg font-bold text-white flex items-center gap-2">
                        <i class="fas fa-user-plus text-blue-500"></i> Register New Teacher
                    </h3>
                    <button id="close-modal-btn" class="text-gray-400 hover:text-white">
                        <i class="fas fa-times text-lg"></i>
                    </button>
                </div>
                <form id="add-teacher-form" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Full Name</label>
                        <input type="text" id="teacher-name" required placeholder="e.g. Dr. A. K. Sharma" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Email / Username</label>
                        <input type="email" id="teacher-email" required placeholder="e.g. sharma@college.edu" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Password</label>
                        <input type="password" id="teacher-password" required minlength="4" placeholder="Minimum 4 characters" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Department</label>
                            <input type="text" id="teacher-dept" placeholder="e.g. Computer Science" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Role</label>
                            <select id="teacher-role" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                                <option value="teacher">Teacher</option>
                                <option value="admin">Administrator</option>
                            </select>
                        </div>
                    </div>
                    <div class="pt-4 border-t border-gray-700 flex justify-end gap-3">
                        <button type="button" id="cancel-modal-btn" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Cancel</button>
                        <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2 rounded-lg text-sm shadow-sm transition-colors">Save Account</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Reset Password Modal -->
        <div id="reset-teacher-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
            <div class="bg-cardbg border border-gray-700 rounded-xl max-w-md w-full p-6 shadow-2xl relative">
                <div class="flex items-center justify-between border-b border-gray-700 pb-4 mb-4">
                    <h3 class="text-lg font-bold text-white flex items-center gap-2">
                        <i class="fas fa-key text-amber-500"></i> Reset Teacher Password
                    </h3>
                    <button id="close-reset-modal-btn" class="text-gray-400 hover:text-white">
                        <i class="fas fa-times text-lg"></i>
                    </button>
                </div>
                <form id="reset-teacher-form" class="space-y-4">
                    <input type="hidden" id="reset-teacher-id">
                    <div>
                        <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">Teacher Name</label>
                        <input type="text" id="reset-teacher-name-display" disabled class="w-full bg-darkbg/50 border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-400 cursor-not-allowed">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-gray-300 uppercase mb-1">New Password</label>
                        <input type="password" id="reset-teacher-new-password" required minlength="4" placeholder="Enter new password (min 4 chars)" class="w-full bg-darkbg border border-gray-700 rounded-lg px-3.5 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500">
                    </div>
                    <div class="pt-4 border-t border-gray-700 flex justify-end gap-3">
                        <button type="button" id="cancel-reset-modal-btn" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Cancel</button>
                        <button type="submit" class="bg-amber-600 hover:bg-amber-700 text-white font-medium px-5 py-2 rounded-lg text-sm shadow-sm transition-colors">Update Password</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    let allTeachers = [];
    const tableBody = document.getElementById('teachers-table-body');
    const searchInput = document.getElementById('teacher-search-input');
    const countBadge = document.getElementById('teacher-count-badge');
    const modal = document.getElementById('add-teacher-modal');
    const resetModal = document.getElementById('reset-teacher-modal');

    async function loadTeachers() {
        try {
            allTeachers = await api.getTeachers();
            renderTable(allTeachers);
        } catch (err) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-6 text-center text-red-400">
                        Failed to load teacher directory: ${err.message}
                    </td>
                </tr>
            `;
        }
    }

    function renderTable(list) {
        countBadge.textContent = `Total Faculty Accounts: ${list.length}`;
        if (list.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-8 text-center text-gray-500">
                        No teachers found. Click 'Add Teacher' to create a faculty account.
                    </td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = list.map(t => {
            const isAdmin = t.role === 'admin';
            const roleBadge = isAdmin
                ? `<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-900/60 text-purple-300 border border-purple-700/50">Admin</span>`
                : `<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-900/60 text-blue-300 border border-blue-700/50">Teacher</span>`;

            return `
                <tr class="hover:bg-gray-800/40 transition-colors">
                    <td class="py-3.5 px-4 font-medium text-white flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full ${isAdmin ? 'bg-purple-600/20 text-purple-400' : 'bg-blue-600/20 text-blue-400'} flex items-center justify-center font-bold text-xs shrink-0">
                            <i class="fas ${isAdmin ? 'fa-user-shield' : 'fa-user-tie'}"></i>
                        </div>
                        <div>
                            <div>${t.name}</div>
                        </div>
                    </td>
                    <td class="py-3.5 px-4 font-mono text-xs text-gray-300">${t.email}</td>
                    <td class="py-3.5 px-4 text-gray-300">${t.department || 'Faculty'}</td>
                    <td class="py-3.5 px-4">${roleBadge}</td>
                    <td class="py-3.5 px-4 text-right">
                        ${t.email === 'admin@college.edu' ? '<span class="text-xs text-gray-500 italic">Protected</span>' : `
                            <button data-id="${t.id}" data-name="${t.name}" class="reset-pwd-btn text-amber-400 hover:text-amber-300 p-1.5 rounded hover:bg-amber-900/30 transition-colors mr-1" title="Reset Password">
                                <i class="fas fa-key"></i>
                            </button>
                            <button data-id="${t.id}" data-name="${t.name}" class="delete-teacher-btn text-red-400 hover:text-red-300 p-1.5 rounded hover:bg-red-900/30 transition-colors" title="Delete Account">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        `}
                    </td>
                </tr>
            `;
        }).join('');

        // Attach reset password listeners
        tableBody.querySelectorAll('.reset-pwd-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                const name = btn.getAttribute('data-name');
                document.getElementById('reset-teacher-id').value = id;
                document.getElementById('reset-teacher-name-display').value = name;
                document.getElementById('reset-teacher-new-password').value = '';
                resetModal.classList.remove('hidden');
            });
        });

        // Attach delete listeners
        tableBody.querySelectorAll('.delete-teacher-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.getAttribute('data-id');
                const name = btn.getAttribute('data-name');
                if (confirm(`Are you sure you want to delete account for '${name}'?`)) {
                    try {
                        await api.deleteTeacher(id);
                        showToast(`Deleted teacher account for '${name}'`, 'success');
                        loadTeachers();
                    } catch (err) {
                        showToast(`Failed to delete teacher: ${err.message}`, 'error');
                    }
                }
            });
        });
    }

    // Search filter
    searchInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        const filtered = allTeachers.filter(t => 
            t.name.toLowerCase().includes(q) || t.email.toLowerCase().includes(q) || (t.department && t.department.toLowerCase().includes(q))
        );
        renderTable(filtered);
    });

    // Add Teacher Modal controls
    document.getElementById('add-teacher-btn').addEventListener('click', () => modal.classList.remove('hidden'));
    document.getElementById('close-modal-btn').addEventListener('click', () => modal.classList.add('hidden'));
    document.getElementById('cancel-modal-btn').addEventListener('click', () => modal.classList.add('hidden'));

    // Reset Password Modal controls
    document.getElementById('close-reset-modal-btn').addEventListener('click', () => resetModal.classList.add('hidden'));
    document.getElementById('cancel-reset-modal-btn').addEventListener('click', () => resetModal.classList.add('hidden'));

    // Submit Add Teacher form
    document.getElementById('add-teacher-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            name: document.getElementById('teacher-name').value,
            email: document.getElementById('teacher-email').value,
            password: document.getElementById('teacher-password').value,
            department: document.getElementById('teacher-dept').value || "Faculty",
            role: document.getElementById('teacher-role').value || "teacher"
        };
        try {
            await api.addTeacher(payload);
            showToast(`Added new teacher '${payload.name}'`, 'success');
            modal.classList.add('hidden');
            document.getElementById('add-teacher-form').reset();
            loadTeachers();
        } catch (err) {
            showToast(`Error adding teacher: ${err.message}`, 'error');
        }
    });

    // Submit Reset Password form
    document.getElementById('reset-teacher-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('reset-teacher-id').value;
        const name = document.getElementById('reset-teacher-name-display').value;
        const newPassword = document.getElementById('reset-teacher-new-password').value;

        try {
            await api.resetTeacherPassword(id, newPassword);
            showToast(`Password for '${name}' reset successfully`, 'success');
            resetModal.classList.add('hidden');
        } catch (err) {
            showToast(`Error resetting password: ${err.message}`, 'error');
        }
    });

    // Load initial data
    loadTeachers();
}
