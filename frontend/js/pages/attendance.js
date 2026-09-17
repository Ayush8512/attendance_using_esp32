import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    async render(container, queryParams = '') {
        const params = new URLSearchParams(queryParams);
        const preselectRoll = params.get('roll_no') || '';

        container.innerHTML = `
            <div class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 class="text-3xl font-bold text-white">Attendance Records</h2>
                    <p class="text-gray-400 mt-1">Search, filter by subject/date, and email attendance sheets to teachers.</p>
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
            <div class="bg-cardbg rounded-xl border border-gray-700 p-4 mb-6 flex flex-wrap gap-4 items-end shadow-md">
                <div class="flex-1 min-w-[180px]">
                    <label class="block text-xs font-medium text-gray-400 mb-1">Filter by Student</label>
                    <select id="filter-student" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                        <option value="">All Students</option>
                    </select>
                </div>
                <div class="flex-1 min-w-[180px]">
                    <label class="block text-xs font-medium text-gray-400 mb-1">Filter by Subject</label>
                    <select id="filter-subject" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                        <option value="">All Subjects</option>
                    </select>
                </div>
                <div class="flex-1 min-w-[150px]">
                    <label class="block text-xs font-medium text-gray-400 mb-1">Filter by Date</label>
                    <input type="date" id="filter-date" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
                </div>
                <div class="flex gap-2">
                    <button id="btn-filter" class="bg-highlight hover:bg-red-600 text-white px-5 py-2 rounded-lg font-medium h-[38px] transition-colors flex items-center gap-2 text-sm">
                        <i class="fas fa-filter"></i> Apply Filter
                    </button>
                    <button id="btn-reset-filter" class="bg-gray-700 hover:bg-gray-600 text-gray-300 px-4 py-2 rounded-lg font-medium h-[38px] transition-colors text-sm">
                        Reset
                    </button>
                </div>
            </div>

            <!-- Table -->
            <div class="bg-cardbg rounded-xl border border-gray-700 overflow-hidden shadow-lg">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse" id="attendance-table">
                        <thead>
                            <tr class="text-gray-400 text-xs uppercase bg-gray-800 bg-opacity-50 border-b border-gray-700">
                                <th class="py-4 px-6 font-medium">Date</th>
                                <th class="py-4 px-6 font-medium">Time</th>
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
                        This generates an official <strong>.xlsx Excel Attendance Sheet</strong> for this subject and automatically emails it as an attachment to the professor.
                    </p>

                    <form id="end-class-form" class="space-y-4">
                        <div>
                            <label class="block text-xs font-medium text-gray-300 mb-1">Subject Name *</label>
                            <input type="text" id="modal-subject" required placeholder="e.g. Mathematics, Material Science" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm">
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

            const students = studentsRes.students || studentsRes || [];
            const studentSelect = document.getElementById('filter-student');
            const subjectSelect = document.getElementById('filter-subject');
            
            if (Array.isArray(students)) {
                students.forEach(s => {
                    const option = document.createElement('option');
                    option.value = s.roll_no;
                    option.textContent = `${s.name} (${s.roll_no})`;
                    if (preselectRoll && s.roll_no === preselectRoll) {
                        option.selected = true;
                    }
                    studentSelect.appendChild(option);
                });
            }

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
                    const rollNo = document.getElementById('filter-student').value;
                    const subject = document.getElementById('filter-subject').value;
                    const date = document.getElementById('filter-date').value;
                    
                    const res = await api.getAttendance(rollNo, date, subject);
                    const records = res.records || res || [];
                    currentRecords = Array.isArray(records) ? records : [];
                    
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

                    tbody.innerHTML = currentRecords.map(r => `
                        <tr class="border-b border-gray-700 hover:bg-gray-800 transition-colors">
                            <td class="py-4 px-6 text-gray-300 font-mono">${r.date}</td>
                            <td class="py-4 px-6 text-gray-300 font-mono">${r.time}</td>
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
                    `).join('');
                } catch (e) {
                    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-red-400">Error loading records: ${e.message}</td></tr>`;
                }
            };

            document.getElementById('btn-filter').addEventListener('click', loadRecords);
            document.getElementById('btn-reset-filter').addEventListener('click', () => {
                document.getElementById('filter-student').value = '';
                document.getElementById('filter-subject').value = '';
                document.getElementById('filter-date').value = '';
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
                const submitBtn = document.getElementById('btn-submit-end-class');
                const origText = submitBtn.innerHTML;

                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Generating & Emailing...';

                try {
                    const fd = new FormData();
                    fd.append('subject', sub);
                    fd.append('teacher_email', email);
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
                const csvHeader = "Date,Time,Subject,Name,Roll No,Status\n";
                const csvRows = currentRecords.map(r => 
                    `"${r.date}","${r.time}","${(r.subject || 'General').replace(/"/g, '""')}","${(r.name || '').replace(/"/g, '""')}","${r.roll_no}","${r.status || 'Present'}"`
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

