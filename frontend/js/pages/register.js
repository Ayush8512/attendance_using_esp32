import { api } from '../api.js';
import { showToast } from '../components/toast.js';

export default {
    render(container, queryParams = '') {
        const params = new URLSearchParams(queryParams);
        const initRoll = params.get('roll_no') || '';
        const initName = params.get('name') || '';
        const initSection = params.get('section') || '';

        container.innerHTML = `
            <div class="max-w-3xl mx-auto">
                <div class="flex items-center justify-between mb-6">
                    <div>
                        <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                            <i class="fas fa-user-plus text-highlight"></i> Enroll Student Biometrics
                        </h2>
                        <p class="text-gray-400 mt-1">Official College Roster Integration (A1–G4) with 1-to-1 Device & Face Security.</p>
                    </div>
                    <a href="#students" class="text-sm text-gray-400 hover:text-white px-3 py-1.5 border border-gray-700 hover:border-gray-500 rounded-lg transition-colors">
                        <i class="fas fa-arrow-left mr-1"></i> Back
                    </a>
                </div>
                
                <div class="bg-cardbg rounded-xl border border-gray-700 p-6 shadow-lg">
                    <form id="register-form" class="space-y-6">
                        <!-- Auto-lookup Alert -->
                        <div id="roster-lookup-banner" class="hidden p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-300 text-xs flex items-center gap-2">
                            <i class="fas fa-check-circle text-base text-green-400"></i>
                            <span id="roster-lookup-text">Official student record verified in college roster!</span>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <!-- Left Column -->
                            <div class="space-y-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-400 mb-1">Roll Number / Student ID *</label>
                                    <div class="relative">
                                        <input type="text" id="roll_no" value="${initRoll}" required class="w-full px-4 py-2 rounded-lg font-mono uppercase bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm" placeholder="e.g. A1-01 or 2401100100001">
                                        <span id="lookup-spinner" class="absolute right-3 top-2.5 text-gray-400 hidden"><i class="fas fa-spinner fa-spin"></i></span>
                                    </div>
                                    <p class="text-[11px] text-gray-500 mt-1">Type roll number to auto-fill official name and section from roster.</p>
                                </div>

                                <div>
                                    <label class="block text-sm font-medium text-gray-400 mb-1">Full Name *</label>
                                    <input type="text" id="name" value="${initName}" required class="w-full px-4 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-sm uppercase" placeholder="e.g. ABHINAV SINGH">
                                </div>

                                <div class="grid grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-xs font-medium text-gray-400 mb-1">Branch</label>
                                        <select id="branch_code" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                            <option value="">Select Branch</option>
                                            <option value="A">A - CSE</option>
                                            <option value="B">B - ECE</option>
                                            <option value="C">C - IPE</option>
                                            <option value="D">D - ME</option>
                                            <option value="E">E - ICE</option>
                                            <option value="F">F - EE</option>
                                            <option value="G">G - CE</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-xs font-medium text-gray-400 mb-1">Section</label>
                                        <select id="section" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                            <option value="">Select Section</option>
                                        </select>
                                    </div>
                                </div>

                                <div class="grid grid-cols-2 gap-3">
                                    <div>
                                        <label class="block text-xs font-medium text-gray-400 mb-1">Year (1-4)</label>
                                        <input type="number" id="year" min="1" max="4" value="1" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs">
                                    </div>
                                    <div>
                                        <label class="block text-xs font-medium text-gray-400 mb-1">Class Roll No</label>
                                        <input type="text" id="class_roll_no" class="w-full px-3 py-2 rounded-lg bg-darkbg border border-gray-600 text-white focus:outline-none focus:border-highlight text-xs font-mono" placeholder="e.g. 1">
                                    </div>
                                </div>
                            </div>

                            <!-- Right Column: Face Photo -->
                            <div class="space-y-4 flex flex-col">
                                <label class="block text-sm font-medium text-gray-400 mb-1">Face Biometric Selfie *</label>
                                
                                <div class="flex-1 min-h-[180px] border-2 border-dashed border-gray-600 rounded-xl flex flex-col items-center justify-center p-4 bg-gray-800 bg-opacity-30 relative overflow-hidden group">
                                    <img id="photo-preview" class="absolute inset-0 w-full h-full object-cover hidden" alt="Preview">
                                    <div id="photo-placeholder" class="text-center">
                                        <i class="fas fa-camera text-4xl text-gray-500 mb-2"></i>
                                        <p class="text-sm text-gray-400">Click to upload or capture face selfie</p>
                                    </div>
                                    <input type="file" id="photo-upload" accept="image/*" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10">
                                </div>
                                
                                <div class="flex justify-between items-center mt-2">
                                    <span id="file-name" class="text-xs text-gray-500 truncate max-w-[200px]">No photo chosen</span>
                                    <button type="button" id="btn-camera" class="text-xs text-highlight hover:text-white transition-colors">
                                        <i class="fas fa-video mr-1"></i> Use Webcam
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Webcam Container -->
                        <div id="webcam-container" class="hidden flex-col items-center border border-gray-600 rounded-lg p-4 bg-gray-900">
                            <video id="webcam-video" autoplay playsinline class="w-full max-w-sm rounded-lg mb-4 bg-black"></video>
                            <button type="button" id="btn-capture" class="bg-highlight hover:bg-red-600 text-white px-6 py-2 rounded-full font-medium transition-colors text-sm">
                                <i class="fas fa-camera mr-2"></i> Capture Selfie
                            </button>
                            <canvas id="webcam-canvas" class="hidden"></canvas>
                        </div>

                        <div class="pt-4 border-t border-gray-700 flex justify-end gap-4">
                            <button type="reset" class="px-6 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-700 transition-colors text-sm">Clear</button>
                            <button type="submit" class="px-6 py-2 rounded-lg bg-highlight hover:bg-red-600 text-white font-medium transition-colors flex items-center shadow text-sm">
                                <i class="fas fa-save mr-2"></i> Save & Lock Profile
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        const form = document.getElementById('register-form');
        const rollInput = document.getElementById('roll_no');
        const nameInput = document.getElementById('name');
        const branchSelect = document.getElementById('branch_code');
        const sectionSelect = document.getElementById('section');
        const yearInput = document.getElementById('year');
        const classRollInput = document.getElementById('class_roll_no');
        const lookupBanner = document.getElementById('roster-lookup-banner');
        const lookupText = document.getElementById('roster-lookup-text');
        const lookupSpinner = document.getElementById('lookup-spinner');

        const photoUpload = document.getElementById('photo-upload');
        const photoPreview = document.getElementById('photo-preview');
        const photoPlaceholder = document.getElementById('photo-placeholder');
        const fileName = document.getElementById('file-name');
        
        let selectedFile = null;

        // Populate section dropdown based on branch
        const updateSections = (selectedBranch, preselect = '') => {
            sectionSelect.innerHTML = '<option value="">Select Section</option>';
            const branches = selectedBranch ? [selectedBranch] : ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
            branches.forEach(b => {
                for (let y = 1; y <= 4; y++) {
                    const sec = `${b}${y}`;
                    const opt = document.createElement('option');
                    opt.value = sec;
                    opt.textContent = `Section ${sec}`;
                    if (preselect && preselect === sec) opt.selected = true;
                    sectionSelect.appendChild(opt);
                }
            });
        };
        updateSections('', initSection);

        branchSelect.addEventListener('change', () => {
            updateSections(branchSelect.value, sectionSelect.value);
        });

        // Auto-lookup logic
        let lookupTimer = null;
        const doRosterLookup = async (roll) => {
            if (!roll || roll.length < 2) {
                lookupBanner.classList.add('hidden');
                return;
            }
            lookupSpinner.classList.remove('hidden');
            try {
                const res = await api.lookupRosterStudent(roll);
                if (res.found && res.student) {
                    const s = res.student;
                    nameInput.value = s.name;
                    if (s.branch_code) branchSelect.value = s.branch_code;
                    updateSections(s.branch_code, s.section);
                    if (s.section) sectionSelect.value = s.section;
                    if (s.year) yearInput.value = s.year;
                    if (s.class_roll_no) classRollInput.value = s.class_roll_no;

                    lookupBanner.className = 'p-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-300 text-xs flex items-center gap-2';
                    lookupText.innerHTML = `<strong>Official Roster Match:</strong> ${s.name} • ${s.branch_name} (${s.section}) • Class Roll #${s.class_roll_no}`;
                    lookupBanner.classList.remove('hidden');
                } else {
                    lookupBanner.className = 'p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2';
                    lookupText.textContent = `Roll number not in official roster. You can enter details manually.`;
                    lookupBanner.classList.remove('hidden');
                }
            } catch (e) {
                console.warn("Lookup error", e);
            } finally {
                lookupSpinner.classList.add('hidden');
            }
        };

        rollInput.addEventListener('input', (e) => {
            clearTimeout(lookupTimer);
            lookupTimer = setTimeout(() => doRosterLookup(e.target.value.trim().toUpperCase()), 400);
        });

        if (initRoll) {
            doRosterLookup(initRoll);
        }

        // Photo Upload & Preview
        photoUpload.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                selectedFile = e.target.files[0];
                fileName.textContent = selectedFile.name;
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    photoPreview.src = e.target.result;
                    photoPreview.classList.remove('hidden');
                    photoPlaceholder.classList.add('hidden');
                };
                reader.readAsDataURL(selectedFile);
                stopWebcam();
            }
        });

        // Webcam controls
        const btnCamera = document.getElementById('btn-camera');
        const webcamContainer = document.getElementById('webcam-container');
        const video = document.getElementById('webcam-video');
        const canvas = document.getElementById('webcam-canvas');
        const btnCapture = document.getElementById('btn-capture');
        let stream = null;

        const stopWebcam = () => {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            webcamContainer.classList.add('hidden');
        };

        btnCamera.addEventListener('click', async () => {
            if (webcamContainer.classList.contains('hidden')) {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
                    video.srcObject = stream;
                    webcamContainer.classList.remove('hidden');
                    webcamContainer.classList.add('flex');
                } catch (err) {
                    showToast("Error accessing camera: " + err.message, "error");
                }
            } else {
                stopWebcam();
            }
        });

        btnCapture.addEventListener('click', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            
            canvas.toBlob((blob) => {
                selectedFile = new File([blob], "capture.jpg", { type: "image/jpeg" });
                fileName.textContent = "Camera Capture";
                
                photoPreview.src = URL.createObjectURL(blob);
                photoPreview.classList.remove('hidden');
                photoPlaceholder.classList.add('hidden');
                
                stopWebcam();
            }, 'image/jpeg');
        });

        // Form Submit
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (!selectedFile) {
                showToast("Please upload or capture a face photo.", "error");
                return;
            }

            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Registering...';
            submitBtn.disabled = true;

            const formData = new FormData();
            formData.append('name', nameInput.value.trim().toUpperCase());
            formData.append('roll_no', rollInput.value.trim().toUpperCase());
            if (branchSelect.value) formData.append('branch_code', branchSelect.value);
            if (sectionSelect.value) formData.append('section', sectionSelect.value);
            if (yearInput.value) formData.append('year', yearInput.value);
            if (classRollInput.value) formData.append('class_roll_no', classRollInput.value.trim());
            formData.append('photo', selectedFile);

            try {
                const res = await api.registerStudent(formData);
                showToast(res.message || "Student registered successfully!", "success");
                setTimeout(() => window.location.hash = '#students', 1200);
            } catch (error) {
                showToast(error.message, "error");
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }
};

