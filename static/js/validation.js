/* =========================================================
   REGISTRATION FORM VALIDATION
   Interior Design Management System
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("registrationForm");

    if (!form) {
        return;
    }


    const name = document.getElementById("name");
    const email = document.getElementById("email");
    const phone = document.getElementById("phone");
    const password = document.getElementById("password");
    const confirmPassword =
        document.getElementById("confirm_password");
    const terms = document.getElementById("terms");


    const nameError = document.getElementById("nameError");
    const emailError = document.getElementById("emailError");
    const phoneError = document.getElementById("phoneError");
    const passwordError =
        document.getElementById("passwordError");
    const confirmPasswordError =
        document.getElementById("confirmPasswordError");
    const termsError =
        document.getElementById("termsError");


    /* =========================
       ERROR MESSAGE
       ========================= */

    function showError(input, errorElement, message) {

        input.classList.add("input-error");
        input.classList.remove("input-success");

        errorElement.textContent = message;
    }


    /* =========================
       SUCCESS
       ========================= */

    function showSuccess(input, errorElement) {

        input.classList.remove("input-error");
        input.classList.add("input-success");

        errorElement.textContent = "";
    }


    /* =========================
       NAME VALIDATION
       ========================= */

    function validateName() {

        const value = name.value.trim();

        if (value === "") {

            showError(
                name,
                nameError,
                "Please enter your full name."
            );

            return false;
        }


        if (value.length < 3) {

            showError(
                name,
                nameError,
                "Name must contain at least 3 characters."
            );

            return false;
        }


        if (value.length > 50) {

            showError(
                name,
                nameError,
                "Name must not exceed 50 characters."
            );

            return false;
        }


        const namePattern =
            /^[A-Za-z]+(?:[ '.-][A-Za-z]+)*$/;


        if (!namePattern.test(value)) {

            showError(
                name,
                nameError,
                "Name can contain letters, spaces, dots, apostrophes or hyphens only."
            );

            return false;
        }


        showSuccess(name, nameError);

        return true;
    }


    /* =========================
       EMAIL VALIDATION
       ========================= */

    function validateEmail() {

        const value = email.value.trim();


        if (value === "") {

            showError(
                email,
                emailError,
                "Please enter your email address."
            );

            return false;
        }


        const emailPattern =
            /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;


        if (!emailPattern.test(value)) {

            showError(
                email,
                emailError,
                "Please enter a valid email address."
            );

            return false;
        }


        showSuccess(email, emailError);

        return true;
    }


    /* =========================
       PHONE VALIDATION
       ========================= */

    function validatePhone() {

        const value = phone.value.trim();


        if (value === "") {

            showError(
                phone,
                phoneError,
                "Please enter your mobile number."
            );

            return false;
        }


        const phonePattern =
            /^[6-9][0-9]{9}$/;


        if (!phonePattern.test(value)) {

            showError(
                phone,
                phoneError,
                "Enter a valid 10-digit Indian mobile number."
            );

            return false;
        }


        showSuccess(phone, phoneError);

        return true;
    }


    /* =========================
       PASSWORD VALIDATION
       ========================= */

    function validatePassword() {

        const value = password.value;


        if (value === "") {

            showError(
                password,
                passwordError,
                "Please enter a password."
            );

            return false;
        }


        if (value.length < 8) {

            showError(
                password,
                passwordError,
                "Password must contain at least 8 characters."
            );

            return false;
        }


        const upperCase =
            /[A-Z]/;

        const lowerCase =
            /[a-z]/;

        const number =
            /[0-9]/;

        const special =
            /[^A-Za-z0-9]/;


        if (!upperCase.test(value)) {

            showError(
                password,
                passwordError,
                "Password must contain at least one uppercase letter."
            );

            return false;
        }


        if (!lowerCase.test(value)) {

            showError(
                password,
                passwordError,
                "Password must contain at least one lowercase letter."
            );

            return false;
        }


        if (!number.test(value)) {

            showError(
                password,
                passwordError,
                "Password must contain at least one number."
            );

            return false;
        }


        if (!special.test(value)) {

            showError(
                password,
                passwordError,
                "Password must contain at least one special character."
            );

            return false;
        }


        showSuccess(password, passwordError);

        return true;
    }


    /* =========================
       CONFIRM PASSWORD
       ========================= */

    function validateConfirmPassword() {

        const value = confirmPassword.value;


        if (value === "") {

            showError(
                confirmPassword,
                confirmPasswordError,
                "Please confirm your password."
            );

            return false;
        }


        if (value !== password.value) {

            showError(
                confirmPassword,
                confirmPasswordError,
                "Passwords do not match."
            );

            return false;
        }


        showSuccess(
            confirmPassword,
            confirmPasswordError
        );

        return true;
    }


    /* =========================
       TERMS
       ========================= */

    function validateTerms() {

        if (!terms.checked) {

            termsError.textContent =
                "Please accept the Terms & Conditions.";

            return false;
        }


        termsError.textContent = "";

        return true;
    }


    /* =========================
       LIVE VALIDATION
       ========================= */

    name.addEventListener(
        "input",
        validateName
    );

    email.addEventListener(
        "input",
        validateEmail
    );

    phone.addEventListener(
        "input",
        function () {

            // Allow numbers only
            this.value =
                this.value.replace(/\D/g, "");

            // Maximum 10 digits
            this.value =
                this.value.substring(0, 10);

            validatePhone();
        }
    );


    password.addEventListener(
        "input",
        function () {

            validatePassword();

            if (confirmPassword.value !== "") {
                validateConfirmPassword();
            }

        }
    );


    confirmPassword.addEventListener(
        "input",
        validateConfirmPassword
    );


    terms.addEventListener(
        "change",
        validateTerms
    );


    /* =========================
       FORM SUBMISSION
       ========================= */

    form.addEventListener(
        "submit",
        function (event) {

            const validName =
                validateName();

            const validEmail =
                validateEmail();

            const validPhone =
                validatePhone();

            const validPassword =
                validatePassword();

            const validConfirmPassword =
                validateConfirmPassword();

            const validTerms =
                validateTerms();


            const formIsValid =
                validName &&
                validEmail &&
                validPhone &&
                validPassword &&
                validConfirmPassword &&
                validTerms;


            if (!formIsValid) {

                event.preventDefault();

                // Find first invalid field
                const firstError =
                    form.querySelector(".input-error");

                if (firstError) {

                    firstError.focus();

                }

                return false;
            }

        }
    );

});