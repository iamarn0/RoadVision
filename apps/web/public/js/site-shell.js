(function (window, document) {
    "use strict";

    var navItems = [
        { id: "home", href: "/", label: "Home" },
        { id: "about", href: "/about", label: "About" },
        { id: "service", href: "/services", label: "Services" },
        { id: "project", href: "/projects", label: "Projects" },
        { id: "contact", href: "/contact", label: "Contact" },
        { id: "login", href: "/login", label: "Sign in" }
    ];

    var services = [
        { href: "/services/traffic-analysis", label: "Traffic Analysis" },
        { href: "/services/anpr-recognition", label: "ANPR Recognition" },
        { href: "/services/road-condition-ai", label: "Road Condition AI" },
        { href: "/services/highway-cctv-intel", label: "Highway CCTV Intel" },
        { href: "/services/fleet-dashcam-survey", label: "Fleet Dashcam Survey" }
    ];

    function navLinks(active) {
        return navItems.map(function (item) {
            var cls = item.id === active ? "nav-item nav-link active" : "nav-item nav-link";
            return '<a href="' + item.href + '" class="' + cls + '">' + item.label + "</a>";
        }).join("");
    }

    function writeChrome(active) {
        document.write(
            '<div id="spinner" class="show bg-white position-fixed translate-middle w-100 vh-100 top-50 start-50 d-flex align-items-center justify-content-center">' +
                '<div class="spinner-border text-primary" style="width: 3rem; height: 3rem;" role="status"><span class="sr-only">Loading...</span></div>' +
            "</div>" +
            '<div class="container-fluid bg-dark px-5">' +
                '<div class="row gx-4 d-none d-lg-flex">' +
                    '<div class="col-lg-6 text-start">' +
                        '<div class="h-100 d-inline-flex align-items-center py-3 me-4"><div class="btn-sm-square rounded-circle bg-primary me-2"><small class="fa fa-map-marker-alt text-white"></small></div><small>Kolkata, West Bengal</small></div>' +
                        '<div class="h-100 d-inline-flex align-items-center py-3"><div class="btn-sm-square rounded-circle bg-primary me-2"><small class="fa fa-envelope-open text-white"></small></div><small>info@roadvision.tech</small></div>' +
                    "</div>" +
                    '<div class="col-lg-6 text-end">' +
                        '<div class="h-100 d-inline-flex align-items-center py-3 me-4"><div class="btn-sm-square rounded-circle bg-primary me-2"><small class="fa fa-phone-alt text-white"></small></div><small><a class="text-white" href="tel:+919831933297">+91 9831933297</a></small></div>' +
                        '<div class="h-100 d-inline-flex align-items-center py-3"><div class="btn-sm-square rounded-circle bg-primary me-2"><small class="far fa-clock text-white"></small></div><small>24/7 Customer Support</small></div>' +
                    "</div>" +
                "</div>" +
            "</div>" +
            '<nav class="navbar navbar-expand-lg bg-white navbar-light sticky-top p-0 px-4 px-lg-5">' +
                '<a href="/" class="navbar-brand d-flex align-items-center"><h2 class="m-0 text-primary">RoadVision</h2></a>' +
                '<button type="button" class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#navbarCollapse"><span class="navbar-toggler-icon"></span></button>' +
                '<div class="collapse navbar-collapse" id="navbarCollapse">' +
                    '<div class="navbar-nav ms-auto py-4 py-lg-0">' + navLinks(active) + "</div>" +
                    '<div class="h-100 d-lg-inline-flex align-items-center d-none">' +
                        '<a class="btn btn-square rounded-circle bg-light text-primary me-2" href="https://www.linkedin.com/" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn"><i class="fab fa-linkedin-in"></i></a>' +
                        '<a class="btn btn-square rounded-circle bg-light text-primary me-0" href="mailto:info@roadvision.tech" aria-label="Email"><i class="fa fa-envelope"></i></a>' +
                    "</div>" +
                "</div>" +
            "</nav>"
        );
    }

    function writePageHeader(title, current) {
        document.write(
            '<div class="container-fluid page-header py-5 mb-5">' +
                '<div class="container py-5">' +
                    '<h1 class="display-3 text-white mb-3 animated slideInDown">' + title + "</h1>" +
                    '<nav aria-label="breadcrumb animated slideInDown">' +
                        '<ol class="breadcrumb mb-0">' +
                            '<li class="breadcrumb-item"><a class="text-white" href="/">Home</a></li>' +
                            '<li class="breadcrumb-item text-white active" aria-current="page">' + current + "</li>" +
                        "</ol>" +
                    "</nav>" +
                "</div>" +
            "</div>"
        );
    }

    function writeFooter() {
        var serviceLinks = services.map(function (item) {
            return '<a class="btn btn-link" href="' + item.href + '">' + item.label + "</a>";
        }).join("");

        document.write(
            '<div class="container-fluid bg-dark text-secondary footer mt-5 py-5 wow fadeIn" data-wow-delay="0.1s">' +
                '<div class="container py-5"><div class="row g-5">' +
                    '<div class="col-lg-3 col-md-6">' +
                        '<h5 class="text-light mb-4">Address</h5>' +
                        '<p class="mb-2"><i class="fa fa-map-marker-alt me-3"></i>Kolkata, West Bengal, India</p>' +
                        '<p class="mb-2"><i class="fa fa-phone-alt me-3"></i><a class="text-secondary" href="tel:+919831933297">+91 9831933297</a></p>' +
                        '<p class="mb-2"><i class="fa fa-envelope me-3"></i><a class="text-secondary" href="mailto:info@roadvision.tech">info@roadvision.tech</a></p>' +
                    "</div>" +
                    '<div class="col-lg-3 col-md-6"><h5 class="text-light mb-4">Services</h5>' + serviceLinks + "</div>" +
                    '<div class="col-lg-3 col-md-6"><h5 class="text-light mb-4">Quick Links</h5>' +
                        '<a class="btn btn-link" href="/about">About Us</a>' +
                        '<a class="btn btn-link" href="/contact">Contact Us</a>' +
                        '<a class="btn btn-link" href="/services">Our Services</a>' +
                        '<a class="btn btn-link" href="/projects">Our Projects</a>' +
                        '<a class="btn btn-link" href="/login">Open Console</a>' +
                    "</div>" +
                    '<div class="col-lg-3 col-md-6"><h5 class="text-light mb-4">Newsletter</h5>' +
                        "<p>Get updates on traffic AI, ANPR, and road condition monitoring.</p>" +
                        '<form id="newsletter-form" class="position-relative w-100">' +
                            '<input id="newsletter-email" class="form-control bg-transparent border-secondary w-100 py-3 ps-4 pe-5" type="email" name="email" placeholder="Your email" required>' +
                            '<button type="submit" class="btn btn-primary py-2 position-absolute top-0 end-0 mt-2 me-2">Sign up</button>' +
                        "</form>" +
                        '<p id="newsletter-status" class="small mt-3 mb-0"></p>' +
                    "</div>" +
                "</div></div>" +
            "</div>" +
            '<div class="container-fluid py-4" style="background: #000000;">' +
                '<div class="container"><div class="row"><div class="col-md-12 text-center text-md-start mb-3 mb-md-0">' +
                    '&copy; <a class="border-bottom" href="/">RoadVision</a>, All Right Reserved.' +
                "</div></div></div>" +
            "</div>" +
            '<a href="#" class="btn btn-lg btn-primary btn-lg-square rounded-circle back-to-top"><i class="bi bi-arrow-up"></i></a>'
        );

        document.addEventListener("submit", function (event) {
            var form = event.target;
            if (!form || form.id !== "newsletter-form") return;
            event.preventDefault();
            var input = document.getElementById("newsletter-email");
            var status = document.getElementById("newsletter-status");
            var email = input ? String(input.value || "").trim() : "";
            submitLead({ type: "newsletter", email: email }, status);
        });
    }

    function submitLead(payload, statusEl) {
        if (statusEl) statusEl.textContent = "Sending…";
        return fetch("/api/contact", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).then(function (response) {
            return response.json().then(function (data) {
                var message = data && data.message ? data.message : "Something went wrong.";
                if (statusEl) {
                    statusEl.textContent = message;
                    statusEl.className = "small mt-3 mb-0 " + (data && data.ok ? "text-success" : "text-danger");
                }
                return data;
            });
        }).catch(function () {
            if (statusEl) {
                statusEl.textContent = "Unable to send right now. Email info@roadvision.tech.";
                statusEl.className = "small mt-3 mb-0 text-danger";
            }
        });
    }

    function slugFromPath(prefix) {
        var path = window.location.pathname.replace(/\/+$/, "");
        if (path === prefix) return "";
        if (path.indexOf(prefix + "/") !== 0) return "";
        return path.slice(prefix.length + 1);
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function renderList(items) {
        return "<ul class='mb-4'>" + items.map(function (item) {
            return "<li class='mb-2'>" + item + "</li>";
        }).join("") + "</ul>";
    }

    function writeNotFound() {
        writePageHeader("Page Not Found", "404");
        document.write(
            '<div class="container-xxl py-5"><div class="container text-center">' +
                '<h1 class="display-5 mb-4">This page is not available</h1>' +
                '<p class="mb-4">The link may be outdated. Browse our services, projects, or send us a message.</p>' +
                '<a class="btn btn-primary rounded-pill py-3 px-5 me-3" href="/services">Services</a>' +
                '<a class="btn btn-outline-primary rounded-pill py-3 px-5" href="/contact">Contact</a>' +
            "</div></div>"
        );
    }

    function writeServiceDetail() {
        var slug = slugFromPath("/services");
        var item = window.RV_CONTENT && window.RV_CONTENT.services ? window.RV_CONTENT.services[slug] : null;
        if (!item) {
            writeNotFound();
            return;
        }
        document.title = item.title + " | RoadVision";
        writePageHeader(item.title, "Services");
        document.write(
            '<div class="container-xxl py-5"><div class="container"><div class="row g-5">' +
                '<div class="col-lg-7">' +
                    '<div class="bg-primary mb-3" style="width: 60px; height: 2px;"></div>' +
                    "<h1 class='display-5 mb-4'>" + escapeHtml(item.title) + "</h1>" +
                    "<p class='mb-4'>" + item.intro + "</p>" +
                    item.sections.map(function (section) {
                        return "<h4 class='mb-3'>" + escapeHtml(section.heading) + "</h4><p class='mb-4'>" + section.body + "</p>";
                    }).join("") +
                    (item.bullets ? "<h4 class='mb-3'>What you get</h4>" + renderList(item.bullets) : "") +
                    '<a class="btn btn-primary rounded-pill py-3 px-5" href="/contact?service=' + encodeURIComponent(slug) + '">Talk to an engineer</a>' +
                "</div>" +
                '<div class="col-lg-5">' +
                    '<div class="bg-light p-4 p-lg-5 h-100">' +
                        '<img class="img-fluid mb-4" src="' + item.icon + '" alt="">' +
                        "<h4 class='mb-3'>Need this on your cameras?</h4>" +
                        "<p class='mb-4'>Unikorn engineers design, deploy, and support the full stack: cameras, ANPR, networking, and the RoadVision console.</p>" +
                        '<a class="btn btn-dark w-100 py-3 mb-3" href="/contact?service=' + encodeURIComponent(slug) + '">Request a site survey</a>' +
                        '<a class="btn btn-outline-dark w-100 py-3" href="/projects">See related projects</a>' +
                    "</div>" +
                "</div>" +
            "</div></div></div>"
        );
    }

    function writeProjectDetail() {
        var slug = slugFromPath("/projects");
        var item = window.RV_CONTENT && window.RV_CONTENT.projects ? window.RV_CONTENT.projects[slug] : null;
        if (!item) {
            writeNotFound();
            return;
        }
        document.title = item.title + " | RoadVision";
        writePageHeader(item.title, "Projects");
        document.write(
            '<div class="container-xxl py-5"><div class="container"><div class="row g-5">' +
                '<div class="col-lg-6"><img class="img-fluid w-100" src="' + item.image + '" alt="' + escapeHtml(item.title) + '"></div>' +
                '<div class="col-lg-6">' +
                    '<p class="text-primary mb-2">' + escapeHtml(item.category) + "</p>" +
                    "<h1 class='display-5 mb-4'>" + escapeHtml(item.headline) + "</h1>" +
                    "<p class='mb-4'>" + item.summary + "</p>" +
                    "<h4 class='mb-3'>Challenge</h4><p class='mb-4'>" + item.challenge + "</p>" +
                    "<h4 class='mb-3'>What we deployed</h4>" + renderList(item.scope) +
                    "<h4 class='mb-3'>Outcome</h4><p class='mb-4'>" + item.outcome + "</p>" +
                    '<a class="btn btn-primary rounded-pill py-3 px-5 me-3" href="/contact">Start a similar project</a>' +
                    '<a class="btn btn-outline-primary rounded-pill py-3 px-5" href="/projects">All projects</a>' +
                "</div>" +
            "</div></div></div>"
        );
    }

    function bindContactForm() {
        var form = document.getElementById("contact-form");
        if (!form) return;
        var params = new URLSearchParams(window.location.search);
        var preset = params.get("service");
        var serviceField = form.elements.namedItem("service");
        if (preset && serviceField) serviceField.value = preset;
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            var status = document.getElementById("contact-status");
            var payload = {
                type: "inquiry",
                name: (form.elements.namedItem("name") || {}).value,
                email: (form.elements.namedItem("email") || {}).value,
                phone: (form.elements.namedItem("phone") || {}).value,
                service: (form.elements.namedItem("service") || {}).value,
                message: (form.elements.namedItem("message") || {}).value
            };
            var button = form.querySelector('button[type="submit"]');
            if (button) button.disabled = true;
            submitLead(payload, status).then(function (data) {
                if (button) button.disabled = false;
                if (data && data.ok) form.reset();
            });
        });
    }

    window.RV = {
        writeChrome: writeChrome,
        writePageHeader: writePageHeader,
        writeFooter: writeFooter,
        writeServiceDetail: writeServiceDetail,
        writeProjectDetail: writeProjectDetail,
        writeNotFound: writeNotFound,
        bindContactForm: bindContactForm
    };
})(window, document);
