document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".celebration-info").forEach(celebration => {
        let button = celebration.querySelector(".toggle-details");
        let details = celebration.querySelector(".celebration-details");

        button.addEventListener("click", function () {
            if (details.style.maxHeight === "0px" || details.style.maxHeight === "") {
                // Expand the section
                details.style.maxHeight = "500px"; // Automatically adjust to content height
                details.style.visibility = 'visible'
                button.textContent = "➖ skrýt detaily";
                this.classList.add("expanded");
            } else {
                // Collapse the section
                details.style.maxHeight = "";
                details.style.visibility = 'hidden'
                button.textContent = "➕ zobrazit detaily";
                this.classList.remove("expanded");
            }
        });
    });
});


