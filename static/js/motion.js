document.addEventListener("DOMContentLoaded", function () {
    const targets = document.querySelectorAll(
        "main > section:not(.dashboard-section), " +
        "main > .container, " +
        "main .hero-content, " +
        "main .about-hero-content, " +
        "main .services-hero-content, " +
        "main .gallery-hero-content, " +
        "main .designer-hero-content, " +
        "main .section-heading, " +
        "main .feature-card, " +
        "main .service-card, " +
        "main .service-large-card, " +
        "main .process-card, " +
        "main .designer-card, " +
        "main .benefit-card, " +
        "main .gallery-item, " +
        "main .product-card, " +
        "main .mission-card, " +
        "main .user-card, " +
        "main .auth-card, " +
        "main .register-card, " +
        "main .consultation-form-card, " +
        "main .quotation-card, " +
        "main .tracking-card"
    );

    if (!targets.length) return;

    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reducedMotion || !("IntersectionObserver" in window)) return;

    const observer = new IntersectionObserver(function (entries, currentObserver) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-visible");
            currentObserver.unobserve(entry.target);
        });
    }, {
        threshold: 0.12,
        rootMargin: "0px 0px -35px 0px"
    });

    targets.forEach(function (target) {
        target.classList.add("motion-reveal");
        observer.observe(target);
    });
});
