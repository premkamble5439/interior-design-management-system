function closeFlash(button) {

    const popup = button.parentElement;

    popup.style.opacity = "0";

    popup.style.transform = "translateX(100px)";

    popup.style.transition = "0.3s";

    setTimeout(function () {

        popup.remove();

    }, 300);
}


/* Automatically hide popup after 5 seconds */

document.addEventListener("DOMContentLoaded", function () {

    const popups = document.querySelectorAll(".flash-popup");

    popups.forEach(function (popup) {

        setTimeout(function () {

            popup.style.opacity = "0";

            popup.style.transform = "translateX(100px)";

            popup.style.transition = "0.3s";

            setTimeout(function () {

                popup.remove();

            }, 300);

        }, 5000);

    });

});