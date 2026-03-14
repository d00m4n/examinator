/* quiz.js — keyboard & selection logic for STIT examinator */

function showConfirm() { document.getElementById('confirmOverlay').style.display = 'flex'; }
function hideConfirm() { document.getElementById('confirmOverlay').style.display = 'none'; }
function submitExam() {
    document.getElementById('finishAction').value = 'Finish Exam';
    document.getElementById('quizForm').submit();
}

function updateSelection(input) {
    if (input.type === 'radio') {
        document.querySelectorAll('input[name="' + input.name + '"]').forEach(function(r) {
            r.closest('.answer-option').classList.toggle('is-selected', r.checked);
        });
    } else {
        input.closest('.answer-option').classList.toggle('is-selected', input.checked);
    }
}

function initQuiz() {
    // Estat inicial (respostes guardades)
    document.querySelectorAll('.answer-option input:checked').forEach(function(inp) {
        inp.closest('.answer-option').classList.add('is-selected');
    });

    // Clicks sobre les opcions
    document.querySelectorAll('.answer-option').forEach(function(label) {
        label.addEventListener('click', function() {
            var inp = this.querySelector('input');
            setTimeout(function() { updateSelection(inp); }, 0);
        });
    });
}

// Inicialitza quan el DOM estigui llest
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initQuiz);
} else {
    initQuiz();
}

document.addEventListener('keydown', function(e) {
    var overlay = document.getElementById('confirmOverlay');
    if (!overlay) return;

    if (e.key === 'Escape') {
        if (overlay.style.display === 'flex') hideConfirm();
        return;
    }
    if (overlay.style.display === 'flex') {
        if (e.key === 'Enter') { e.preventDefault(); submitExam(); }
        return;
    }
    if (e.target.tagName === 'INPUT' && e.target.type === 'text') return;
    if (e.target.tagName === 'TEXTAREA') return;

    // Tecles 1-9
    if (e.key && e.key.length === 1 && e.key >= '1' && e.key <= '9') {
        e.preventDefault();
        var options = document.querySelectorAll('.answer-option input');
        var target = options[parseInt(e.key) - 1];
        if (!target) return;
        if (target.type === 'radio') {
            target.checked = true;
        } else {
            target.checked = !target.checked;
        }
        updateSelection(target);
        var label = target.closest('.answer-option');
        label.classList.add('key-flash');
        setTimeout(function() { label.classList.remove('key-flash'); }, 250);
        return;
    }

    // Navegació: Seguent
    if (e.key === 'ArrowRight' || e.key === 'Enter' || e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        var btnNext = document.getElementById('btnNext');
        if (btnNext) { btnNext.click(); } else { showConfirm(); }
        return;
    }

    // Navegació: Anterior
    if (e.key === 'ArrowLeft' || e.key === 'q' || e.key === 'Q') {
        e.preventDefault();
        var btnPrev = document.getElementById('btnPrev');
        if (btnPrev) { btnPrev.click(); }
    }
});
