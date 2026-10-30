// Progressive enhancement only: every feature also works without JavaScript.
document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', function () {
    var diocese = document.getElementById('dieceze');
    if (diocese) {
        diocese.addEventListener('change', function () { diocese.form.submit(); });
    }
});
