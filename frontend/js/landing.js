document.addEventListener('DOMContentLoaded', () => {
    // Navbar Scroll Effect
    const header = document.querySelector('.header');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });

    // Mobile Menu Toggle
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');
    const headerInner = document.querySelector('.nav-inner');

    if (navToggle) {
        navToggle.addEventListener('click', () => {
            navToggle.classList.toggle('active');
            navLinks.classList.toggle('open');
            document.body.style.overflow = navLinks.classList.contains('open') ? 'hidden' : '';
        });
    }

    // Close menu on link click
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('open');
            navToggle.classList.remove('active');
            document.body.style.overflow = '';
        });
    });

    // Live Ticker Animation Logic
    const tickerItems = [
        "Physics Question #992 just solved!",
        "Calculus Expert online now.",
        "Chemistry assignment completed.",
        "Economics solution delivered.",
        "Programming help active."
    ];
    let tickerIndex = 0;
    const tickerEl = document.querySelector('.ticker-item');
    if (tickerEl) {
        setInterval(() => {
            tickerIndex = (tickerIndex + 1) % tickerItems.length;
            tickerEl.style.opacity = 0;
            setTimeout(() => {
                tickerEl.textContent = tickerItems[tickerIndex];
                tickerEl.style.opacity = 1;
            }, 500);
        }, 3000);
    }

    // Real stats are handled by loadStats() in index.html

    // Reveal on Scroll (Intersection Observer)
    const reveals = document.querySelectorAll('.reveal');
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    reveals.forEach(reveal => revealObserver.observe(reveal));

    // Smooth Scroll for Navigation
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const target = document.getElementById(targetId);
            if (target) {
                const headerOffset = 80;
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: "smooth"
                });
            }
        });
    });
});
