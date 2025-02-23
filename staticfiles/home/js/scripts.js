document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".toggle-details").forEach(button => {
        button.addEventListener("click", function () {
            let details = celebration.querySelector(".celebration-details");
            if (details.style.display === "none" || details.style.display === "") {
                details.style.display = "block";
                this.textContent = "➖ Skrýt detaily";
            } else {
                details.style.display = "none";
                this.textContent = "➕ Zobrazit detaily";
            }
        });
    });
});
