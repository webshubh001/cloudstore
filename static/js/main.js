/**
 * CloudStore — Main JavaScript
 * Handles: sidebar, drag-and-drop, theme toggle, file preview,
 * dark mode persistence, and AJAX helpers.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ── Dark / Light Theme Toggle ─────────────────────────────────────────
    const html = document.documentElement;
    const themeToggleBtn = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');

    const applyTheme = (theme) => {
        html.setAttribute('data-theme', theme);
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
        }
        localStorage.setItem('cloudstore-theme', theme);
    };

    // Load saved theme
    const savedTheme = localStorage.getItem('cloudstore-theme') || 'dark';
    applyTheme(savedTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const current = html.getAttribute('data-theme');
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    // ── Sidebar Toggle (mobile) ───────────────────────────────────────────
    const sidebar = document.getElementById('sidebar');
    const sidebarOpen = document.getElementById('sidebarOpen');
    const sidebarClose = document.getElementById('sidebarClose');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    const openSidebar = () => {
        sidebar?.classList.add('open');
        sidebarOverlay?.classList.add('open');
        document.body.style.overflow = 'hidden';
    };

    const closeSidebar = () => {
        sidebar?.classList.remove('open');
        sidebarOverlay?.classList.remove('open');
        document.body.style.overflow = '';
    };

    sidebarOpen?.addEventListener('click', openSidebar);
    sidebarClose?.addEventListener('click', closeSidebar);
    sidebarOverlay?.addEventListener('click', closeSidebar);

    // Close on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeSidebar();
    });

    // ── Drag & Drop Upload ─────────────────────────────────────────────────
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInputModal');
    const filePreviewList = document.getElementById('filePreviewList');

    if (dropZone && fileInput) {
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
            dropZone.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); });
            document.body.addEventListener(evt, (e) => { e.preventDefault(); });
        });

        // Visual feedback
        ['dragenter', 'dragover'].forEach(evt => {
            dropZone.addEventListener(evt, () => dropZone.classList.add('drag-over'));
        });

        ['dragleave', 'drop'].forEach(evt => {
            dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'));
        });

        // Handle drop
        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                updateFileInput(files);
            }
        });

        // Handle click-to-browse
        dropZone.addEventListener('click', (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                showFilePreviews(fileInput.files);
            }
        });

        function updateFileInput(files) {
            const dt = new DataTransfer();
            for (let f of files) dt.items.add(f);
            fileInput.files = dt.files;
            showFilePreviews(files);
        }

        function showFilePreviews(files) {
            filePreviewList.innerHTML = '';
            const contentDiv = dropZone.querySelector('.dropzone-content');
            if (files.length > 0 && contentDiv) {
                contentDiv.style.display = 'none';
            }
            for (let file of files) {
                const item = document.createElement('div');
                item.className = 'file-preview-item';
                const icon = getFileIcon(file.name, file.type);
                item.innerHTML = `<i class="fas ${icon}"></i><span>${truncate(file.name, 24)}</span><span class="text-muted">${formatSize(file.size)}</span>`;
                filePreviewList.appendChild(item);
            }
        }
    }

    // ── Upload Form: progress indicator ───────────────────────────────────
    const uploadForm = document.getElementById('uploadForm');
    const uploadBtn = document.getElementById('uploadBtn');

    if (uploadForm && uploadBtn) {
        uploadForm.addEventListener('submit', () => {
            const fileInput = document.getElementById('fileInputModal');
            if (fileInput && fileInput.files.length === 0) {
                return; // Don't show spinner if no files
            }
            uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Uploading...';
            uploadBtn.disabled = true;
        });
    }

    // ── Auto-close toasts ──────────────────────────────────────────────────
    document.querySelectorAll('.alert-toast').forEach((toast) => {
        setTimeout(() => {
            toast.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            setTimeout(() => toast.remove(), 400);
        }, 5000);
    });

    // ── New Folder Modal — focus input ─────────────────────────────────────
    const newFolderModal = document.getElementById('newFolderModal');
    const folderNameInput = document.getElementById('folderNameInput');

    if (newFolderModal && folderNameInput) {
        newFolderModal.addEventListener('shown.bs.modal', () => {
            folderNameInput.focus();
        });
    }

    // ── Global search shortcut (Ctrl+K / Cmd+K) ────────────────────────────
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('globalSearch');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
    });

    // ── Tooltips initialization ────────────────────────────────────────────
    const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipEls.forEach(el => {
        new bootstrap.Tooltip(el, { trigger: 'hover' });
    });

    // ── Confirm delete links ────────────────────────────────────────────────
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', (e) => {
            if (!confirm(el.dataset.confirm)) e.preventDefault();
        });
    });

    // ── Animate stat cards on scroll ───────────────────────────────────────
    const statCards = document.querySelectorAll('.stat-card');
    if ('IntersectionObserver' in window && statCards.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.animation = 'fadeIn 0.5s ease forwards';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        statCards.forEach(card => observer.observe(card));
    }

    // ── File count animation (dashboard) ──────────────────────────────────
    document.querySelectorAll('.stat-card-value').forEach(el => {
        const target = parseInt(el.textContent.trim());
        if (!isNaN(target) && target > 0) {
            let start = 0;
            const step = Math.ceil(target / 30);
            const timer = setInterval(() => {
                start = Math.min(start + step, target);
                el.textContent = start;
                if (start >= target) clearInterval(timer);
            }, 25);
        }
    });

    console.info('🌩️ CloudStore JS initialized');
});

// ── Utility Functions ────────────────────────────────────────────────────────

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 ** 3) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    return (bytes / (1024 ** 3)).toFixed(2) + ' GB';
}

function truncate(str, maxLen) {
    return str.length > maxLen ? str.substring(0, maxLen - 1) + '…' : str;
}

function getFileIcon(name, mime) {
    const ext = name.split('.').pop().toLowerCase();
    if (mime?.startsWith('image/')) return 'fa-file-image';
    if (mime?.startsWith('video/')) return 'fa-file-video';
    if (mime?.startsWith('audio/')) return 'fa-file-audio';
    if (mime?.includes('pdf')) return 'fa-file-pdf';
    if (['zip','rar','tar','gz','7z'].includes(ext)) return 'fa-file-zipper';
    if (['xls','xlsx'].includes(ext)) return 'fa-file-excel';
    if (['doc','docx'].includes(ext)) return 'fa-file-word';
    if (['ppt','pptx'].includes(ext)) return 'fa-file-powerpoint';
    if (['py','js','ts','html','css','java','cpp','c','go'].includes(ext)) return 'fa-file-code';
    if (['txt','md','csv'].includes(ext)) return 'fa-file-lines';
    return 'fa-file';
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => showFlashToast('Copied to clipboard!', 'success'));
    } else {
        const el = document.createElement('textarea');
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        showFlashToast('Copied!', 'success');
    }
}

function showFlashToast(msg, type = 'info') {
    const container = document.querySelector('.messages-container') || (() => {
        const c = document.createElement('div');
        c.className = 'messages-container';
        document.body.appendChild(c);
        return c;
    })();

    const toast = document.createElement('div');
    toast.className = `alert-toast alert-toast-${type}`;
    toast.innerHTML = `
        <div class="alert-toast-icon"><i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'}"></i></div>
        <div class="alert-toast-body">${msg}</div>
        <button class="alert-toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
    `;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 400); }, 3000);
}
