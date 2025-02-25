document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".celebration-info").forEach(celebration => {
        let button = celebration.querySelector(".toggle-details");
        let details = celebration.querySelector(".celebration-details");

        button.addEventListener("click", function () {
            if (details.style.maxHeight === "0px" || details.style.maxHeight === "") {
                // Expand the section
                details.style.maxHeight = "500px"; // Automatically adjust to content height
                details.style.visibility = 'visible'
                this.classList.add("expanded");
                button.textContent = "➖ skrýt detailní doporučení";
            } else {
                // Collapse the section
                details.style.maxHeight = "0px";
                details.style.visibility = 'hidden';
                this.classList.remove("expanded");
                button.textContent = "➕ zobrazit detailní doporučení";
            }
        });
    });
});


