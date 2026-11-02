document.addEventListener("DOMContentLoaded", function () {
    const chat = document.querySelector("[data-help-chat]");
    if (!chat) return;

    const toggle = chat.querySelector(".help-chat-toggle");
    const panel = chat.querySelector("#help-chat-panel");
    const close = chat.querySelector(".help-chat-close");
    const messages = chat.querySelector("[data-chat-messages]");
    const form = chat.querySelector("[data-chat-form]");
    const input = chat.querySelector("#help-chat-input");

    const pages = {
        home: {label: "Home", href: "/"},
        services: {label: "Browse services", href: "/services"},
        designers: {label: "Meet our designers", href: "/designers"},
        consultation: {label: "Book a consultation", href: "/consultation"},
        register: {label: "Create an account", href: "/register"},
        login: {label: "Log in", href: "/login"},
        quotation: {label: "Request a quotation", href: "/quotation"},
        tracking: {label: "View project tracking", href: "/project-tracking"},
        store: {label: "Visit the store", href: "/store"},
        cart: {label: "View your cart", href: "/cart"}
    };

    const responses = [
        {
            terms: ["consult", "appointment", "book", "meeting"],
            text: "To request a design consultation, open the consultation page and submit your project details. You may be asked to sign in first.",
            page: "consultation"
        },
        {
            terms: ["designer", "professional", "who can design"],
            text: "Browse the Designers page to explore available professionals. You can also request a consultation to discuss your project.",
            page: "designers"
        },
        {
            terms: ["service", "offer", "what do you do"],
            text: "Explore our services to see the interior design options offered by the studio.",
            page: "services"
        },
        {
            terms: ["register", "sign up", "create account", "new account"],
            text: "Create a customer account using the Register page. An account lets you use customer features such as consultations and project updates.",
            page: "register"
        },
        {
            terms: ["login", "log in", "sign in", "password"],
            text: "Use the Login page for your customer account. Staff members should use their role-specific login link.",
            page: "login"
        },
        {
            terms: ["quotation", "quote", "estimate", "price"],
            text: "Use the quotation page to submit the details of the work you have in mind and request a quote.",
            page: "quotation"
        },
        {
            terms: ["track", "project status", "project update", "progress"],
            text: "Sign in to your customer account, then open project tracking to review project updates.",
            page: "tracking"
        },
        {
            terms: ["store", "product", "buy", "shop", "cart", "payment", "pay", "order"],
            text: "Browse products in the Store, add items to your cart, and continue to checkout. Sign in if prompted.",
            page: "store",
            secondPage: "cart"
        },
        {
            terms: ["contact", "support", "help"],
            text: "You can reach the studio using the contact details in the footer. For site guidance, ask me about services, consultations, accounts, or projects.",
            page: "home"
        }
    ];

    function setOpen(isOpen) {
        panel.hidden = !isOpen;
        toggle.setAttribute("aria-expanded", String(isOpen));
        if (isOpen) input.focus();
    }

    function addMessage(text, kind, page, secondPage) {
        const message = document.createElement("div");
        message.className = "help-chat-message " + kind;
        message.appendChild(document.createTextNode(text));

        if (page) {
            message.appendChild(document.createElement("br"));
            const link = document.createElement("a");
            link.href = pages[page].href;
            link.textContent = pages[page].label;
            message.appendChild(link);
        }

        if (secondPage) {
            message.appendChild(document.createTextNode(" or "));
            const link = document.createElement("a");
            link.href = pages[secondPage].href;
            link.textContent = pages[secondPage].label;
            message.appendChild(link);
        }

        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;
    }

    function answerQuestion(question) {
        const normalized = question.toLowerCase();
        const response = responses.find(function (item) {
            return item.terms.some(function (term) {
                return normalized.includes(term);
            });
        });

        if (response) {
            addMessage(response.text, "help-chat-bot", response.page, response.secondPage);
        } else {
            addMessage(
                "I don't have an answer for that yet. Try asking about services, designers, consultations, registration, quotations, projects, or the store.",
                "help-chat-bot",
                "services"
            );
        }
    }

    toggle.addEventListener("click", function () {
        setOpen(panel.hidden);
    });

    close.addEventListener("click", function () {
        setOpen(false);
        toggle.focus();
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        addMessage(question, "help-chat-user");
        input.value = "";
        answerQuestion(question);
        input.focus();
    });

    chat.querySelectorAll("[data-chat-question]").forEach(function (button) {
        button.addEventListener("click", function () {
            const question = button.getAttribute("data-chat-question");
            addMessage(question, "help-chat-user");
            answerQuestion(question);
        });
    });
});
