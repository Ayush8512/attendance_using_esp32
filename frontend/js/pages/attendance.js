import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    async render(container, queryParams = '') {
        const params = new URLSearchParams(queryParams);
        const preselectRoll = params.get('roll_no') || '';

        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-clipboard-check text-highlight"></i> Attendance Records
                    </h2>
                    <p class="text-gray-400 mt-1">Search, filter by branch/section/subject/date, and generate Excel sheets.</p>
                </div>
                <div class="flex items-center gap-3 w-full md:w-auto">
                    <button id="btn-end-class-modal" class="bg-accent hover:bg-blue-900 border border-blue-500/50 text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2 text-sm font-semibold shadow-md">
                        <i class="fas fa-paper-plane text-yellow-400"></i> End Class & Email Sheet
                    </button>
                    <button id="btn-export" class="bg-cardbg border border-gray-600 hover:border-green-500 text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2 text-sm">
                        <i class="fas fa-file-csv text-green-400"></i> Export CSV
                    </button>
                </div>
            </div>

            <!-- Filters -->
            <div class="bg-cardbg rounded-xl border border-gray-700 p-4 mb-6 shadow-md">
                <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 items-end">
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Branch</label>
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
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Section</label>
                        <select id="filter-section" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                            <option value="">All Sections</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Subject</label>
                        <select id="filter-subject" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                            <option value="">All Subjects</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-gray-400 mb-1">Date</label>
                        <input type="date" id="filter-date" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                    </div>
                    <div class="flex gap-2">
                        <button id="btn-filter" class="flex-1 bg-highlight hover:bg-red-600 text-white px-4 py-2 rounded-lg font-medium h-[38px] transition-colors flex items-center justify-center gap-1.5 text-sm">
                            <i class="fas fa-filter"></i> Apply
                        </button>
                        <button id="btn-reset-filter" class="bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-2 rounded-lg font-medium h-[38px] transition-colors text-sm" title="Reset Filters">
                            <i class="fas fa-undo"></i>
                        </button>
                    </div>
                </div>
                <div class="mt-3">
                    <input type="text" id="filter-student-search" placeholder="Search student name or roll number..." class="w-full px-3 py-1.5 rounded-lg bg-darkbg border border-gray-600 text-white text-xs focus:outline-none focus:border-highlight">
                </div>
            </div>

            <!-- Table -->
            <div class="bg-cardbg rounded-xl border border-gray-700 overflow-hidden shadow-lg">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse" id="attendance-table">
                        <thead>
                            <tr class="text-gray-400 text-xs uppercase bg-gray-800 bg-opacity-50 border-b border-gray-700">
                                <th class="py-4 px-6 font-medium">Date & Time</th>
                                <th class="py-4 px-6 font-medium">Branch / Section</th>
                                <th class="py-4 px-6 font-medium">Subject</th>
                                <th class="py-4 px-6 font-medium">Student Name</th>
                                <th class="py-4 px-6 font-medium">Roll Number</th>
                                <th class="py-4 px-6 font-medium">Method</th>
                                <th class="py-4 px-6 font-medium">Status</th>
                            </tr>
                        </thead>
                        <tbody id="attendance-body" class="text-sm">
                            <tr><td colspan="7" class="py-8 text-center text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading records...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- End Class & Email Sheet Modal -->
            <div id="end-class-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
                <div class="bg-cardbg border border-gray-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-5">
                    <div class="flex items-center justify-between border-b border-gray-700 pb-3">
                        <h3 class="text-lg font-bold text-white flex items-center gap-2">
                            <i class="fas fa-envelope-open-text text-highlight"></i> End Class & Send Report
                        </h3>
                        <button id="btn-close-modal" class="text-gray-400 hover:text-white text-lg">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <p class="text-xs text-gray-300">
                        Generates official <strong>.xlsx Excel Sheet</strong> with Branch, Section, Class Roll, and AKTU Roll numbers.
                    </p>

                    <form id="end-class-form" class="space-y-4">
                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Subject Name *</label>
                            <input type="text" id="modal-subject" required placeholder="e.g. Mathematics, Material Science" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                        </div>
                        <div class="grid grid-cols-3 gap-2">
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Year</label>
                                <select id="modal-year" class="w-full px-2 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    <option value="0">All</option>
                                    <option value="1">1st Yr</option>
                                    <option value="2">2nd Yr</option>
                                    <option value="3">3rd Yr</option>
                                    <option value="4">4th Yr</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-gray-300 mb-1">Branch</label>
                                <select id="modal-branch" class="w-full px-2 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    <option value="">All</option>
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
                                <label class="block text-xs font-medium text-gray-300 mb-1">Section</label>
                                <select id="modal-section" class="w-full px-2 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    <option value="">All</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Professor / Teacher Email *</label>
                            <input type="email" id="modal-email" required placeholder="teacher@college.edu" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                        </div>

                        <div class="pt-2 flex justify-end gap-3">
                            <button type="button" id="btn-cancel-modal" class="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-medium">Cancel</button>
                            <button type="submit" id="btn-submit-end-class" class="px-5 py-2 rounded-lg bg-highlight hover:bg-red-600 text-white text-sm font-semibold flex items-center gap-2">
                                <i class="fas fa-file-excel"></i> Generate & Send Sheet
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        let currentRecords = [];

        try {
            const [studentsRes, timetableRes] = await Promise.all([
                api.getStudents().catch(() => ({ students: [] })),
                api.getTimetable().catch(() => null)
            ]);

            const branchSelect = document.getElementById('filter-branch');
            const sectionSelect = document.getElementById('filter-section');
            const modalSection = document.getElementById('modal-section');
            const modalBranch = document.getElementById('modal-branch');
            const modalYear = document.getElementById('modal-year');
            const subjectSelect = document.getElementById('filter-subject');

            // Populate Filter Section Dropdowns (A1 to G4)
            const populateSections = () => {
                sectionSelect.innerHTML = '<option value="">All Sections</option>';
                const selB = branchSelect.value;
                const branches = selB ? [selB] : ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
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
            populateSections();

            // Populate Modal Section Dropdowns based on Modal Branch and Modal Year
            const populateModalSections = () => {
                modalSection.innerHTML = '<option value="">All Sections</option>';
                const selB = modalBranch.value;
                const selY = parseInt(modalYear.value || '0');
                const branches = selB ? [selB] : ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
                const years = selY > 0 ? [selY] : [1, 2, 3, 4];
                branches.forEach(b => {
                    years.forEach(y => {
                        const sec = `${b}${y}`;
                        const opt = document.createElement('option');
                        opt.value = sec;
                        opt.textContent = `Sec ${sec}`;
                        modalSection.appendChild(opt);
                    });
                });
            };
            populateModalSections();

            modalBranch.addEventListener('change', populateModalSections);
            modalYear.addEventListener('change', populateModalSections);

            branchSelect.addEventListener('change', () => {
                populateSections();
                loadRecords();
            });
            sectionSelect.addEventListener('change', () => loadRecords());

            // Populate subjects from timetable schedule
            const knownSubjects = new Set();
            if (timetableRes?.timetable) {
                timetableRes.timetable.forEach(t => {
                    if (t.subject) knownSubjects.add(t.subject);
                });
            }

            const populateSubjectFilter = () => {
                subjectSelect.innerHTML = '<option value="">All Subjects</option>';
                knownSubjects.forEach(sub => {
                    const opt = document.createElement('option');
                    opt.value = sub;
                    opt.textContent = sub;
                    subjectSelect.appendChild(opt);
                });
            };
            populateSubjectFilter();

            // Pre-fill active subject in Modal if lecture is active
            if (timetableRes?.current_slot?.class) {
                document.getElementById('modal-subject').value = timetableRes.current_slot.class.subject || '';
                document.getElementById('modal-email').value = timetableRes.current_slot.class.teacher_email || '';
            }

            const loadRecords = async () => {
                const tbody = document.getElementById('attendance-body');
                tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading records...</td></tr>`;
                
                try {
                    const branch = branchSelect.value;
                    const section = sectionSelect.value;
                    const subject = subjectSelect.value;
                    const date = document.getElementById('filter-date').value;
                    const searchVal = document.getElementById('filter-student-search').value.trim().toLowerCase();
                    const rollNo = preselectRoll || '';
                    
                    const res = await api.getAttendance(rollNo, date, subject, branch, section);
                    let records = res.records || res || [];
                    if (!Array.isArray(records)) records = [];

                    if (searchVal) {
                        records = records.filter(r => 
                            (r.name && r.name.toLowerCase().includes(searchVal)) ||
                            (r.roll_no && r.roll_no.toLowerCase().includes(searchVal)) ||
                            (r.class_roll_no && r.class_roll_no.toLowerCase().includes(searchVal))
                        );
                    }
                    currentRecords = records;
                    
                    // Collect any new subjects found in logs
                    currentRecords.forEach(r => {
                        if (r.subject && !knownSubjects.has(r.subject)) {
                            knownSubjects.add(r.subject);
                            populateSubjectFilter();
                        }
                    });

                    if (currentRecords.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-gray-500">No attendance records found for this filter.</td></tr>`;
                        return;
                    }

                    tbody.innerHTML = currentRecords.map(r => {
                        const secBadge = r.section ? `<span class="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-mono font-semibold">${r.section}</span>` : '<span class="text-xs text-gray-500">-</span>';
                        const branchBadge = r.branch_code ? `<span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-semibold">${r.branch_code}</span>` : '';

                        return `
                            <tr class="border-b border-gray-700 hover:bg-gray-800 transition-colors">
                                <td class="py-4 px-6 text-gray-300 font-mono text-xs">
                                    <span class="font-semibold text-white">${r.date}</span><br/>
                                    <span class="text-gray-400">${r.time}</span>
                                </td>
                                <td class="py-4 px-6">
                                    <div class="flex items-center gap-1.5">
                                        ${branchBadge}
                                        ${secBadge}
                                    </div>
                                </td>
                                <td class="py-4 px-6">
                                    <span class="bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2.5 py-1 rounded text-xs font-semibold capitalize inline-flex items-center gap-1.5">
                                        <i class="fas fa-book-reader text-[10px]"></i> ${r.subject || 'General'}
                                    </span>
                                </td>
                                <td class="py-4 px-6 font-medium text-white">${r.name || '-'}</td>
                                <td class="py-4 px-6 text-gray-300 font-mono">${r.roll_no}</td>
                                <td class="py-4 px-6 text-gray-400">
                                    <span class="bg-gray-700 px-2.5 py-1 rounded text-xs font-mono inline-flex items-center gap-1">
                                        <i class="fas fa-camera text-highlight"></i> Face
                                    </span>
                                </td>
                                <td class="py-4 px-6">
                                    <span class="badge ${r.status === 'Present' ? 'badge-present' : 'badge-absent'}">${r.status || 'Present'}</span>
                                </td>
                            </tr>
                        `;
                    }).join('');
                } catch (e) {
                    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-red-400">Error loading records: ${e.message}</td></tr>`;
                }
            };

            document.getElementById('btn-filter').addEventListener('click', loadRecords);
            document.getElementById('filter-student-search').addEventListener('input', loadRecords);
            document.getElementById('btn-reset-filter').addEventListener('click', () => {
                branchSelect.value = '';
                populateSections();
                sectionSelect.value = '';
                subjectSelect.value = '';
                document.getElementById('filter-date').value = '';
                document.getElementById('filter-student-search').value = '';
                loadRecords();
            });

            // Modal Controls
            const modal = document.getElementById('end-class-modal');
            const openModal = () => modal.classList.remove('hidden');
            const closeModal = () => modal.classList.add('hidden');

            document.getElementById('btn-end-class-modal').addEventListener('click', openModal);
            document.getElementById('btn-close-modal').addEventListener('click', closeModal);
            document.getElementById('btn-cancel-modal').addEventListener('click', closeModal);

            document.getElementById('end-class-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const sub = document.getElementById('modal-subject').value.trim();
                const email = document.getElementById('modal-email').value.trim();
                const sec = document.getElementById('modal-section').value.trim();
                const br = document.getElementById('modal-branch').value.trim();
                const yr = document.getElementById('modal-year').value.trim();
                const submitBtn = document.getElementById('btn-submit-end-class');
                const origText = submitBtn.innerHTML;

                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Generating & Emailing...';

                try {
                    const fd = new FormData();
                    fd.append('subject', sub);
                    fd.append('teacher_email', email);
                    if (sec) fd.append('section', sec);
                    if (br) fd.append('branch', br);
                    if (yr && yr !== '0') fd.append('year', yr);
                    const res = await api.endClass(fd);
                    
                    if (res.download_url) {
                        const a = document.createElement('a');
                        a.href = res.download_url;
                        a.download = res.filename || `Attendance_${sub}.xlsx`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }

                    showToast(res.message || `Attendance report for ${sub} generated!`, res.email_sent ? "success" : "info");
                    closeModal();
                } catch (err) {
                    showToast(`Failed: ${err.message}`, "error");
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = origText;
                }
            });

            // CSV Export
            document.getElementById('btn-export').addEventListener('click', () => {
                if (currentRecords.length === 0) {
                    alert("No records to export.");
                    return;
                }
                const csvHeader = "Date,Time,Branch,Section,Class Roll,Subject,Name,Primary Roll,Status\n";
                const csvRows = currentRecords.map(r => 
                    `"${r.date}","${r.time}","${r.branch_code || ''}","${r.section || ''}","${r.class_roll_no || ''}","${(r.subject || 'General').replace(/"/g, '""')}","${(r.name || '').replace(/"/g, '""')}","${r.roll_no}","${r.status || 'Present'}"`
                ).join("\n");
                
                const blob = new Blob([csvHeader + csvRows], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Attendance_${new Date().toISOString().slice(0, 10)}.csv`;
                a.click();
                URL.revokeObjectURL(url);
            });

            loadRecords();

        } catch (error) {
            console.error("Attendance page error:", error);
        }
    }
};

