/**
 * Won Kyun Koh Blog - Unified Global Script
 * Handles Navigation, Likes, Share Modal, Animations,
 * and Automatic Paragraph Formatting
 */

document.addEventListener('DOMContentLoaded', () => {

    /* =========================================================
       1. MOBILE MENU TOGGLE
    ========================================================= */
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', (e) => {
            e.stopPropagation();
            mobileMenu.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (!mobileMenu.contains(e.target) && !mobileMenuButton.contains(e.target)) {
                mobileMenu.classList.add('hidden');
            }
        });
    }

    /* =========================================================
       2. AUTO FORMAT ARTICLE PARAGRAPHS
       Converts blank lines into proper <p> blocks
    ========================================================= */
    document.querySelectorAll('.article-text').forEach(block => {
        const rawHTML = block.innerHTML.trim();

        const paragraphs = rawHTML
            .split(/\n\s*\n+/)
            .map(p => `<p class="mb-6">${p.replace(/\n/g, '<br>')}</p>`)
            .join('');

        block.innerHTML = paragraphs;
    });

    /* =========================================================
       3. LIKE BUTTON FUNCTIONALITY  (real, persistent counts)

       SYSTEMATIC BY DESIGN — no per-page setup is required.
       Any page that includes this script gets working likes as
       long as each like button looks like:

           <button class="like-button" ...>
               <i class="far fa-heart"></i>
               <span class="like-count">0</span>
           </button>

       The post's identity (its row in the database) is derived
       automatically from the filename, so:
         - a home/list card's "Read More" link  ->  that entry's id
         - the entry page itself                 ->  its own filename
       both map to the SAME id, sharing one count. New posts create
       their own row on the first like (starting at 0) with no SQL.

       Counts live in Supabase and are shared across all visitors.
       The Supabase library is loaded on demand below, so HTML pages
       only need:  <script src="script.js"></script>
       If Supabase isn't configured yet, buttons still work locally
       (not saved) so the site never breaks. One-time backend setup
       lives in supabase-setup.sql.
    ========================================================= */

    // ---- CONFIG: paste these from Supabase -> Project Settings -> API
    const SUPABASE_URL = 'https://llwxxsiftyzreslarvwe.supabase.co';
    const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxsd3h4c2lmdHl6cmVzbGFydndlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI2ODQyMjQsImV4cCI6MjA5ODI2MDIyNH0.nobjUoOZCsp2qlc7eNhWheIveitQMQkJZ3EfaOeFOpI';
    const SUPABASE_LIB = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2';

    const likeButtons = document.querySelectorAll('.like-button');

    if (likeButtons.length) {
        // A stable id for the post a button belongs to (see note above).
        const slugify = (s) =>
            s.split('/').pop().split(/[?#]/)[0].replace(/\.html?$/i, '') || 'home';

        function getPostId(button) {
            const explicit = button.getAttribute('data-post-id');
            if (explicit) return slugify(explicit);

            const card = button.closest('article, .post-card, .featured-post');
            const link = card && card.querySelector('.read-more-link[href]');
            if (link) return slugify(link.getAttribute('href'));

            return slugify(window.location.pathname);
        }

        const likedKey = (postId) => `liked:${postId}`;

        function paintLiked(button, liked) {
            const icon = button.querySelector('i');
            if (liked) {
                icon.classList.replace('far', 'fas');
                icon.style.color = '#ef4444';
                button.setAttribute('data-liked', 'true');
            } else {
                icon.classList.replace('fas', 'far');
                icon.style.color = '';
                button.setAttribute('data-liked', 'false');
            }
        }

        // Tag every button with its id and restore this visitor's own
        // "liked" state immediately — no network needed.
        likeButtons.forEach(button => {
            const postId = getPostId(button);
            button.dataset.postId = postId;
            if (localStorage.getItem(likedKey(postId)) === 'true') {
                paintLiked(button, true);
            }

            button.addEventListener('click', async () => {
                const id = button.dataset.postId;
                const span = button.querySelector('.like-count');
                // Mark this button as user-touched so the initial count load
                // below can't clobber it with a stale server value mid-flight.
                button.dataset.userActed = '1';
                const wasLiked = localStorage.getItem(likedKey(id)) === 'true';
                const delta = wasLiked ? -1 : 1;

                // Optimistic update so the UI feels instant.
                const prevCount = parseInt(span.textContent, 10) || 0;
                span.textContent = Math.max(0, prevCount + delta);
                paintLiked(button, !wasLiked);
                localStorage.setItem(likedKey(id), String(!wasLiked));

                // Wait for the Supabase client before giving up. Previously a
                // click made before the CDN library finished loading returned
                // here as "local-only" and was never saved — so a like made on
                // the home page never showed up on the entry page. Awaiting the
                // shared promise means even an early click persists.
                const client = await clientReady;
                if (!client) return; // not configured / library failed -> local-only

                const { data, error } = await client.rpc('bump_likes', {
                    pid: id,
                    delta
                });

                if (error) {
                    // Roll back the optimistic change if the server rejected it.
                    console.error('Like failed:', error.message);
                    span.textContent = prevCount;
                    paintLiked(button, wasLiked);
                    localStorage.setItem(likedKey(id), String(wasLiked));
                } else if (typeof data === 'number') {
                    span.textContent = data; // trust the authoritative count
                }
            });
        });

        // Load the Supabase library on demand ONCE, shared by clicks and the
        // initial count fetch. Resolves to the client, or null if the backend
        // isn't configured or the library can't load (buttons stay local-only).
        const clientReady = (async () => {
            const configured =
                SUPABASE_URL.startsWith('https://') &&
                !SUPABASE_URL.includes('YOUR-PROJECT');
            if (!configured) return null;

            if (!window.supabase) {
                await new Promise((resolve) => {
                    const tag = document.createElement('script');
                    tag.src = SUPABASE_LIB;
                    tag.onload = resolve;
                    tag.onerror = resolve;
                    document.head.appendChild(tag);
                });
            }
            if (!window.supabase) {
                console.error('Could not load the Supabase library.');
                return null;
            }
            return window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        })();

        // Once the client is ready, fetch live counts for this page's buttons.
        clientReady.then(async (client) => {
            if (!client) return;

            const ids = [...likeButtons].map(b => b.dataset.postId);
            const { data, error } = await client
                .from('likes')
                .select('post_id, count')
                .in('post_id', ids);

            if (error) {
                console.error('Could not load like counts:', error.message);
                return;
            }
            const counts = Object.fromEntries(data.map(r => [r.post_id, r.count]));
            likeButtons.forEach(button => {
                // Don't overwrite a button the visitor just clicked; its own
                // RPC response is the authoritative value.
                if (button.dataset.userActed) return;
                const span = button.querySelector('.like-count');
                const id = button.dataset.postId;
                if (id in counts) span.textContent = counts[id];
            });
        });
    }

    /* =========================================================
       3b. EMAIL SUBSCRIBE  (Buttondown, inline — no popup)

       SYSTEMATIC BY DESIGN — like the likes above, any page that
       includes this script and has the footer form gets a working
       inline signup. The only setting is the username below.

         <form class="footer-subscribe" ...>
             <input type="email" name="email" ...>
             <button type="submit">Subscribe</button>
         </form>
         <p class="footer-subscribe-status"></p>

       The email is POSTed to Buttondown's embed endpoint. A static
       page can't read Buttondown's cross-origin reply without a
       secret API key (which we never ship), so the request is sent
       no-cors and we optimistically confirm. Buttondown's
       double-opt-in email is the real confirmation — keep it ON.
    ========================================================= */

    // ---- CONFIG: your Buttondown username (the ONLY place to set it).
    const BUTTONDOWN_USER = 'andyetwego';

    document.querySelectorAll('form.footer-subscribe').forEach(form => {
        const status = form.parentElement.querySelector('.footer-subscribe-status');
        const button = form.querySelector('button[type="submit"]');

        const say = (msg, ok) => {
            if (!status) return;
            status.textContent = msg;
            status.style.color = ok ? '#2f7a4d' : '#b04a3a';
        };

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const input = form.querySelector('input[name="email"]');
            const email = (input.value || '').trim();
            if (!email) { say('Please enter your email.', false); return; }

            const original = button.textContent;
            button.disabled = true;
            button.textContent = 'Subscribing…';
            say('', true);

            try {
                const body = new URLSearchParams({ email });
                await fetch(
                    `https://buttondown.com/api/emails/embed-subscribe/${BUTTONDOWN_USER}`,
                    { method: 'POST', body, mode: 'no-cors' }
                );
                // no-cors hides the response, so confirm optimistically.
                say('✓ Thanks! Check your inbox to confirm.', true);
                form.reset();
            } catch (err) {
                console.error('Subscribe failed:', err);
                say('Something went wrong — please try again.', false);
            } finally {
                button.disabled = false;
                button.textContent = original;
            }
        });
    });

    /* =========================================================
       4. SHARE MODAL LOGIC
    ========================================================= */
    const modal = document.getElementById('share-modal');
    const shareLinkInput = document.getElementById('share-link');
    const copyButton = document.getElementById('copy-link');

    if (modal) {
        const openLink = document.getElementById('open-link');

        document.querySelectorAll('.share-button').forEach(button => {
            button.addEventListener('click', () => {
                // Prefer the card's "Read More" target; on an entry page that
                // has none, share the current page itself. Either way works
                // with no per-page setup.
                const article = button.closest('article, .post-card, .featured-post');
                const readMore = article?.querySelector('.read-more-link[href]');
                const href = readMore && readMore.getAttribute('href');
                const url = href
                    ? new URL(href, window.location.href).href
                    : window.location.href;

                shareLinkInput.value = url;
                if (openLink) openLink.href = url;
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            });
        });

        document.querySelectorAll('#close-modal, #close-modal-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            });
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        });
    }

    /* =========================================================
       5. COPY LINK (Mobile Compatible)
    ========================================================= */
    if (copyButton) {
        copyButton.addEventListener('click', () => {
            shareLinkInput.select();
            shareLinkInput.setSelectionRange(0, 99999);

            navigator.clipboard.writeText(shareLinkInput.value).then(() => {
                const originalText = copyButton.textContent;
                copyButton.textContent = 'Copied!';
                copyButton.classList.add('bg-green-600');

                setTimeout(() => {
                    copyButton.textContent = originalText;
                    copyButton.classList.remove('bg-green-600');
                }, 2000);
            });
        });
    }

    /* =========================================================
       6. SCROLL ANIMATION
    ========================================================= */
    const animateElements = document.querySelectorAll('.animate-fade-in');
    const observerOptions = { threshold: 0.1 };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    animateElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        observer.observe(el);
    });

});
