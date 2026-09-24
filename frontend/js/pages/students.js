import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    async render(container) {
        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-university text-highlight"></i> Students & College Directory
                    </h2>
                    <p class="text-gray-400 mt-1">7 Branches (A–G) • 28 Sections (A1–G4) • Official IERT College Roster</p>
                </div>
                <div class="flex flex-wrap items-center gap-3 w-full md:w-auto">
                    <!-- Registration Window Switch -->
                    <div id="reg-status-container" class="flex items-center gap-2 bg-cardbg px-3 py-2 rounded-lg border border-gray-700">
                        <span class="text-xs text-gray-400 font-medium">App Registration:</span>
                        <button id="btn-toggle-reg" class="px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition-colors bg-gray-700 text-gray-300">
                            <i class="fas fa-spinner fa-spin"></i> Checking...
                        </button>
                    </div>
                </div>
            </div>

            <!-- Stats Bar -->
            <div id="roster-stats-bar" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 shadow flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center text-lg">
                        <i class="fas fa-users"></i>
                    </div>
                    <div>
                        <p class="text-xs text-gray-400 uppercase font-semibold">Total Roster</p>
                        <p id="stat-total-roster" class="text-xl font-bold text-white">1,706</p>
                    </div>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 shadow flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-green-500/20 text-green-400 flex items-center justify-center text-lg">
                        <i class="fas fa-user-check"></i>
                    </div>
                    <div>
                        <p class="text-xs text-gray-400 uppercase font-semibold">Registered Biometrics</p>
                        <p id="stat-total-registered" class="text-xl font-bold text-white">0</p>
                    </div>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 shadow flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center text-lg">
                        <i class="fas fa-code-branch"></i>
                    </div>
                    <div>
                        <p class="text-xs text-gray-400 uppercase font-semibold">Branches</p>
                        <p class="text-xl font-bold text-white">7 Branches (A–G)</p>
                    </div>
                </div>
                <div class="bg-cardbg rounded-xl border border-gray-700 p-4 shadow flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center text-lg">
                        <i class="fas fa-layer-group"></i>
                    </div>
                    <div>
                        <p class="text-xs text-gray-400 uppercase font-semibold">Sections</p>
                        <p class="text-xl font-bold text-white">28 Sections (A1–G4)</p>
                    </div>
                </div>
            </div>

            <!-- Tab Buttons & Filters -->
            <div class="bg-cardbg rounded-xl border border-gray-700 p-4 mb-6 shadow-md flex flex-col md:flex-row justify-between items-stretch md:items-center gap-4">
                <!-- Tabs -->
                <div class="flex items-center gap-2 border-b md:border-b-0 border-gray-700 pb-3 md:pb-0">
                    <button id="tab-registered" class="px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-highlight text-white flex items-center gap-2 shadow">
                        <i class="fas fa-fingerprint"></i> Registered Biometrics
                    </button>
                    <button id="tab-roster" class="px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-gray-800 text-gray-300 hover:bg-gray-700 flex items-center gap-2">
                        <i class="fas fa-list-ol"></i> College Roster (1,706)
                    </button>
                </div>

                <!-- Filters -->
                <div class="flex flex-wrap items-center gap-3">
                    <div class="w-40">
                        <select id="filter-branch" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                            <option value="">All Branches</option>
                            <option value="A">A - Computer Science (CSE)</option>
                            <option value="B">B - Electronics (ECE)</option>
                            <option value="C">C - Industrial (IPE)</option>
                            <option value="D">D - Mechanical (ME)</option>
                            <option value="E">E - Instrumentation (ICE)</option>
                            <option value="F">F - Electrical (EE)</option>
                            <option value="G">G - Civil (CE)</option>
                        </select>
                    </div>

                    <div class="w-36">
                        <select id="filter-section" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                            <option value="">All Sections</option>
                        </select>
                    </div>

                    <div class="relative flex-1 md:w-56">
                        <i class="fas fa-search absolute left-3 top-3 text-gray-400"></i>
                        <input type="text" id="search-student" placeholder="Search name or roll..." class="w-full pl-9 pr-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                    </div>
                </div>
            </div>

            <!-- Table Container -->
            <div class="bg-cardbg rounded-xl border border-gray-700 overflow-hidden shadow-lg">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse" id="students-table">
                        <thead>
                            <tr class="text-gray-400 text-xs uppercase bg-gray-800 bg-opacity-50 border-b border-gray-700">
                                <th class="py-4 px-6 font-medium">#</th>
                                <th class="py-4 px-6 font-medium">Branch & Section</th>
                                <th class="py-4 px-6 font-medium">Student Name</th>
                                <th class="py-4 px-6 font-medium">Roll Number</th>
                                <th class="py-4 px-6 font-medium">Biometric & Device Status</th>
                                <th class="py-4 px-6 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="students-body" class="text-sm">
                            <tr><td colspan="6" class="py-8 text-center text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading students...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Edit Student Profile Modal -->
            <div id="edit-student-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
                <div class="bg-cardbg border border-gray-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
                    <div class="flex items-center justify-between border-b border-gray-700 pb-3">
                        <h3 class="text-lg font-bold text-white flex items-center gap-2">
                            <i class="fas fa-user-edit text-highlight"></i> Edit Student Profile
                        </h3>
                        <button id="btn-close-edit-student" class="text-gray-400 hover:text-white text-lg">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <form id="edit-student-form" class="space-y-4">
                        <div>
                            <label class="block text-xs font-medium text-gray-400 mb-1">Roll Number</label>
                            <input type="text" id="edit-student-roll" disabled class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 font-mono text-sm cursor-not-allowed">
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Full Name *</label>
                            <input type="text" id="edit-student-name" required class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                        </div>
                        <div class="grid grid-cols-3 gap-2">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Branch</label>
                                <select id="edit-student-branch" class="w-full px-2 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    <option value="A">A (CSE)</option>
                                    <option value="B">B (ECE)</option>
                                    <option value="C">C (IPE)</option>
                                    <option value="D">D (ME)</option>
                                    <option value="E">E (ICE)</option>
                                    <option value="F">F (EE)</option>
                                    <option value="G">G (CE)</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Year</label>
                                <select id="edit-student-year" class="w-full px-2 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    <option value="1">1st Yr</option>
                                    <option value="2">2nd Yr</option>
                                    <option value="3">3rd Yr</option>
                                    <option value="4">4th Yr</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Section</label>
                                <select id="edit-student-section" class="w-full px-2 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    <!-- Populated dynamically -->
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Class Roll Number</label>
                            <input type="text" id="edit-student-classroll" placeholder="e.g. 25" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                        </div>

                        <div class="pt-2 flex justify-end gap-3">
                            <button type="button" id="btn-cancel-edit-student" class="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-medium">Cancel</button>
                            <button type="submit" id="btn-save-edit-student" class="px-5 py-2 rounded-lg bg-highlight hover:bg-red-600 text-white text-sm font-semibold flex items-center gap-2">
                                <i class="fas fa-save"></i> Save Changes
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        // 1. Manage Registration Setting
        const btnToggleReg = document.getElementById('btn-toggle-reg');
        let registrationOpen = true;

        const updateRegBtnUI = (isOpen) => {
            registrationOpen = isOpen;
            if (isOpen) {
                btnToggleReg.className = 'px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30';
                btnToggleReg.innerHTML = '<i class="fas fa-lock-open text-xs"></i> OPEN';
                btnToggleReg.title = 'Click to close registration for all students';
            } else {
                btnToggleReg.className = 'px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30';
                btnToggleReg.innerHTML = '<i class="fas fa-lock text-xs"></i> CLOSED';
                btnToggleReg.title = 'Click to open registration';
            }
        };

        try {
            const settings = await api.getAdminSettings();
            updateRegBtnUI(settings.registration_open);
        } catch (e) {
            btnToggleReg.textContent = 'Unknown';
        }

        btnToggleReg.addEventListener('click', async () => {
            try {
                btnToggleReg.disabled = true;
                const newState = !registrationOpen;
                const res = await api.toggleRegistration(newState);
                updateRegBtnUI(res.registration_open);
                showToast(res.message, "success");
            } catch (err) {
                showToast(`Failed to update setting: ${err.message}`, "error");
            } finally {
                btnToggleReg.disabled = false;
            }
        });

        // 2. Load Stats
        try {
            const stats = await api.getRosterStats();
            document.getElementById('stat-total-roster').textContent = (stats.total_roster || 1706).toLocaleString();
            document.getElementById('stat-total-registered').textContent = `${stats.total_registered || 0} (${stats.overall_percentage || 0}%)`;
        } catch (e) {
            console.warn("Could not load roster stats", e);
        }

        // 3. Populate Section Dropdown
        const branchSelect = document.getElementById('filter-branch');
        const sectionSelect = document.getElementById('filter-section');

        const updateSectionOptions = (selectedBranch) => {
            sectionSelect.innerHTML = '<option value="">All Sections</option>';
            const branches = selectedBranch ? [selectedBranch] : ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
            branches.forEach(b => {
                for (let y = 1; y <= 4; y++) {
                    const sec = `${b}${y}`;
                    const opt = document.createElement('option');
                    opt.value = sec;
                    opt.textContent = `Section ${sec}`;
                    sectionSelect.appendChild(opt);
                }
            });
        };
        updateSectionOptions('');

        branchSelect.addEventListener('change', () => {
            updateSectionOptions(branchSelect.value);
            loadCurrentView();
        });
        sectionSelect.addEventListener('change', () => loadCurrentView());

        // 4. Tab Switcher
        let activeTab = 'registered'; // 'registered' | 'roster'
        const tabRegistered = document.getElementById('tab-registered');
        const tabRoster = document.getElementById('tab-roster');

        tabRegistered.addEventListener('click', () => {
            activeTab = 'registered';
            tabRegistered.className = 'px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-highlight text-white flex items-center gap-2 shadow';
            tabRoster.className = 'px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-gray-800 text-gray-300 hover:bg-gray-700 flex items-center gap-2';
            loadCurrentView();
        });

        tabRoster.addEventListener('click', () => {
            activeTab = 'roster';
            tabRoster.className = 'px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-highlight text-white flex items-center gap-2 shadow';
            tabRegistered.className = 'px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-gray-800 text-gray-300 hover:bg-gray-700 flex items-center gap-2';
            loadCurrentView();
        });

        // 5. Load & Render Logic
        const tbody = document.getElementById('students-body');

        const renderRegisteredStudents = (students) => {
            if (!Array.isArray(students) || students.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500">No registered biometric profiles found matching filter. Students register face biometrics securely from their mobile app.</td></tr>`;
                return;
            }

            tbody.innerHTML = students.map((s, index) => {
                const secBadge = s.section ? `<span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-mono font-semibold">${s.section}</span>` : '<span class="text-xs text-gray-500">-</span>';
                const branchBadge = s.branch_code ? `<span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-semibold">${s.branch_code}</span>` : '';

                return `
                    <tr class="border-b border-gray-700 hover:bg-gray-800 transition-colors group">
                        <td class="py-4 px-6 text-gray-400 font-mono">${index + 1}</td>
                        <td class="py-4 px-6">
                            <div class="flex items-center gap-1.5">
                                ${branchBadge}
                                ${secBadge}
                                ${s.class_roll_no ? `<span class="text-xs text-gray-400 font-mono">#${s.class_roll_no}</span>` : ''}
                            </div>
                        </td>
                        <td class="py-4 px-6 font-medium text-white">
                            <div class="flex items-center gap-3">
                                <div class="w-9 h-9 rounded-full bg-accent flex items-center justify-center text-sm font-bold text-white shadow">
                                    ${s.name ? s.name.charAt(0).toUpperCase() : '?'}
                                </div>
                                <div>
                                    <span class="text-base font-semibold">${s.name}</span>
                                    ${s.created_at ? `<p class="text-xs text-gray-500">Reg: ${s.created_at.slice(0, 10)}</p>` : ''}
                                </div>
                            </div>
                        </td>
                        <td class="py-4 px-6 text-gray-300 font-mono font-medium">${s.roll_no}</td>
                        <td class="py-4 px-6 space-y-1">
                            <div>
                                ${s.is_locked
                                    ? `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                        <i class="fas fa-lock text-[10px]"></i> Locked
                                       </span>`
                                    : `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse">
                                        <i class="fas fa-lock-open text-[10px]"></i> Unlocked
                                       </span>`
                                }
                            </div>
                            <div>
                                ${s.device_bound
                                    ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-gray-700 text-green-300 border border-green-500/30">
                                        <i class="fas fa-mobile-alt text-[10px]"></i> Phone Bound
                                       </span>`
                                    : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-gray-700 text-gray-400">
                                        <i class="fas fa-mobile-alt text-[10px]"></i> No Device
                                       </span>`
                                }
                            </div>
                        </td>
                        <td class="py-4 px-6 text-right space-x-1.5">
                            <button data-roll="${s.roll_no}" data-name="${s.name || ''}" data-branch="${s.branch_code || ''}" data-section="${s.section || ''}" data-year="${s.year || 1}" data-classroll="${s.class_roll_no || ''}" class="btn-edit-student text-green-400 hover:text-white hover:bg-green-600 px-2 py-1 border border-green-500/40 rounded-lg transition-colors text-xs inline-flex items-center gap-1" title="Edit student profile">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                            ${s.is_locked
                                ? `<button data-roll="${s.roll_no}" class="btn-unlock-student text-amber-400 hover:text-white hover:bg-amber-600 px-2 py-1 border border-amber-500/40 rounded-lg transition-colors text-xs inline-flex items-center gap-1" title="Allow student to update face photo">
                                    <i class="fas fa-key"></i> Reset Face
                                   </button>`
                                : `<button data-roll="${s.roll_no}" class="btn-lock-student text-blue-400 hover:text-white hover:bg-blue-600 px-2 py-1 border border-blue-500/40 rounded-lg transition-colors text-xs inline-flex items-center gap-1" title="Lock face biometrics">
                                    <i class="fas fa-lock"></i> Lock
                                   </button>`
                            }
                            <button data-roll="${s.roll_no}" class="btn-reset-dev text-purple-400 hover:text-white hover:bg-purple-600 px-2 py-1 border border-purple-500/40 rounded-lg transition-colors text-xs inline-flex items-center gap-1" title="Reset phone binding so student can login on new phone">
                                <i class="fas fa-sync-alt"></i> Reset Device
                            </button>
                            <a href="#attendance?roll_no=${encodeURIComponent(s.roll_no)}" class="text-highlight hover:text-white px-2 py-1 border border-highlight hover:bg-highlight rounded-lg transition-colors text-xs inline-flex items-center gap-1">
                                <i class="fas fa-calendar-alt"></i> Logs
                            </a>
                            <button data-roll="${s.roll_no}" data-name="${s.name}" class="btn-delete-student text-red-400 hover:text-white hover:bg-red-600 px-2 py-1 border border-red-500/40 rounded-lg transition-colors text-xs inline-flex items-center gap-1">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');

            // Attach action listeners
            tbody.querySelectorAll('.btn-unlock-student').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const roll = btn.getAttribute('data-roll');
                    try {
                        btn.disabled = true;
                        const res = await api.unlockStudent(roll);
                        showToast(res.message || `Biometrics unlocked for ${roll}`, "success");
                        loadCurrentView();
                    } catch (err) {
                        showToast(`Failed to unlock: ${err.message}`, "error");
                        btn.disabled = false;
                    }
                });
            });

            tbody.querySelectorAll('.btn-lock-student').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const roll = btn.getAttribute('data-roll');
                    try {
                        btn.disabled = true;
                        const res = await api.lockStudent(roll);
                        showToast(res.message || `Biometrics locked for ${roll}`, "success");
                        loadCurrentView();
                    } catch (err) {
                        showToast(`Failed to lock: ${err.message}`, "error");
                        btn.disabled = false;
                    }
                });
            });

            tbody.querySelectorAll('.btn-reset-dev').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const roll = btn.getAttribute('data-roll');
                    try {
                        btn.disabled = true;
                        const res = await api.resetStudentDevice(roll);
                        showToast(res.message || `Device binding reset for ${roll}`, "success");
                        loadCurrentView();
                    } catch (err) {
                        showToast(`Failed to reset device: ${err.message}`, "error");
                        btn.disabled = false;
                    }
                });
            });

            tbody.querySelectorAll('.btn-edit-student').forEach(btn => {
                btn.addEventListener('click', () => {
                    const roll = btn.getAttribute('data-roll');
                    const name = btn.getAttribute('data-name');
                    const branch = btn.getAttribute('data-branch') || 'A';
                    const section = btn.getAttribute('data-section') || '';
                    const year = btn.getAttribute('data-year') || '1';
                    const classroll = btn.getAttribute('data-classroll') || '';

                    editRoll.value = roll;
                    editName.value = name;
                    editBranch.value = branch || 'A';
                    editYear.value = year || '1';
                    populateEditSections();
                    if (section) {
                        editSection.value = section;
                    }
                    editClassRoll.value = classroll;
                    editModal.classList.remove('hidden');
                });
            });

            tbody.querySelectorAll('.btn-delete-student').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const roll = btn.getAttribute('data-roll');
                    const name = btn.getAttribute('data-name');
                    if (!confirm(`Delete student '${name}' (${roll})? Biometrics and records will be removed.`)) return;
                    try {
                        await api.deleteStudent(roll);
                        showToast(`Student ${name} deleted successfully.`, "success");
                        loadCurrentView();
                    } catch (err) {
                        showToast(`Failed to delete: ${err.message}`, "error");
                    }
                });
            });
        };

        // Edit Student Modal Controls
        const editModal = document.getElementById('edit-student-modal');
        const editRoll = document.getElementById('edit-student-roll');
        const editName = document.getElementById('edit-student-name');
        const editBranch = document.getElementById('edit-student-branch');
        const editYear = document.getElementById('edit-student-year');
        const editSection = document.getElementById('edit-student-section');
        const editClassRoll = document.getElementById('edit-student-classroll');

        const populateEditSections = () => {
            const b = editBranch.value || 'A';
            const y = editYear.value || '1';
            editSection.innerHTML = '';
            for (let yr = 1; yr <= 4; yr++) {
                const sec = `${b}${yr}`;
                const opt = document.createElement('option');
                opt.value = sec;
                opt.textContent = `Section ${sec}`;
                if (yr == y) opt.selected = true;
                editSection.appendChild(opt);
            }
        };

        editBranch.addEventListener('change', populateEditSections);
        editYear.addEventListener('change', () => {
            const b = editBranch.value || 'A';
            const y = editYear.value || '1';
            editSection.value = `${b}${y}`;
        });

        const closeEditStudentModal = () => editModal.classList.add('hidden');
        document.getElementById('btn-close-edit-student').addEventListener('click', closeEditStudentModal);
        document.getElementById('btn-cancel-edit-student').addEventListener('click', closeEditStudentModal);

        document.getElementById('edit-student-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const roll = editRoll.value;
            const payload = {
                name: editName.value.trim(),
                branch_code: editBranch.value.trim().toUpperCase(),
                year: parseInt(editYear.value) || 1,
                section: editSection.value.trim().toUpperCase(),
                class_roll_no: editClassRoll.value.trim()
            };
            const saveBtn = document.getElementById('btn-save-edit-student');
            const origText = saveBtn.innerHTML;
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Saving...';
            try {
                const res = await api.updateStudent(roll, payload);
                showToast(res.message || `Student ${roll} profile updated successfully!`, "success");
                closeEditStudentModal();
                loadCurrentView();
            } catch (err) {
                showToast(`Update failed: ${err.message}`, "error");
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = origText;
            }
        });

        const renderRosterStudents = (students) => {
            if (!Array.isArray(students) || students.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500">No students found in college roster matching filter.</td></tr>`;
                return;
            }

            tbody.innerHTML = students.map((s, index) => {
                const secBadge = `<span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-mono font-semibold">${s.section}</span>`;
                const branchBadge = `<span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-semibold">${s.branch_code}</span>`;

                return `
                    <tr class="border-b border-gray-700 hover:bg-gray-800 transition-colors">
                        <td class="py-4 px-6 text-gray-400 font-mono">${index + 1}</td>
                        <td class="py-4 px-6">
                            <div class="flex items-center gap-1.5">
                                ${branchBadge}
                                ${secBadge}
                                <span class="text-xs text-gray-400 font-mono">#${s.class_roll_no}</span>
                            </div>
                        </td>
                        <td class="py-4 px-6 font-medium text-white">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300">
                                    ${s.name ? s.name.charAt(0).toUpperCase() : '?'}
                                </div>
                                <span class="text-sm font-semibold">${s.name}</span>
                            </div>
                        </td>
                        <td class="py-4 px-6 text-gray-300 font-mono font-medium">${s.primary_roll_no}</td>
                        <td class="py-4 px-6">
                            ${s.is_registered
                                ? `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                                    <i class="fas fa-check-circle text-xs"></i> Enrolled
                                   </span>`
                                : `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-700 text-gray-400 border border-gray-600">
                                    <i class="fas fa-hourglass-start text-xs"></i> Pending Face
                                   </span>`
                            }
                        </td>
                        <td class="py-4 px-6 text-right">
                            ${s.is_registered
                                ? `<a href="#attendance?roll_no=${encodeURIComponent(s.primary_roll_no)}" class="text-highlight hover:text-white px-2.5 py-1.5 border border-highlight hover:bg-highlight rounded-lg transition-colors text-xs inline-flex items-center gap-1">
                                    <i class="fas fa-calendar-alt"></i> Attendance
                                   </a>`
                                : `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-gray-700/60 text-gray-400 border border-gray-600" title="Student registers face via mobile app">
                                    <i class="fas fa-mobile-alt text-[10px]"></i> Mobile App
                                   </span>`
                            }
                        </td>
                    </tr>
                `;
            }).join('');
        };

        const loadCurrentView = async () => {
            tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading data...</td></tr>`;
            const b = branchSelect.value;
            const sec = sectionSelect.value;
            const q = document.getElementById('search-student').value.trim();

            try {
                if (activeTab === 'registered') {
                    const res = await api.getStudents(b, sec, q);
                    renderRegisteredStudents(res.students || res || []);
                } else {
                    const res = await api.getRosterStudents(sec, b, '', q, 300, 0);
                    renderRosterStudents(res.students || res || []);
                }
            } catch (err) {
                tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-red-400">Failed to load data: ${err.message}</td></tr>`;
            }
        };

        document.getElementById('search-student').addEventListener('input', () => {
            loadCurrentView();
        });

        loadCurrentView();
    }
};


