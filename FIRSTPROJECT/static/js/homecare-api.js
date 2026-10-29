(() => {
    const configNode = document.getElementById("homecare-api-config");
    const apiBase = configNode ? JSON.parse(configNode.textContent || '""') : "";
    const menuButton = document.querySelector("[data-menu-button]");
    const siteMenu = document.querySelector("[data-site-menu]");

    if (menuButton && siteMenu) {
        menuButton.addEventListener("click", () => {
            const isOpen = menuButton.getAttribute("aria-expanded") === "true";
            menuButton.setAttribute("aria-expanded", String(!isOpen));
            siteMenu.classList.toggle("is-open", !isOpen);
        });
    }

    if (!apiBase) return;

    document.querySelectorAll("form[data-api-endpoint]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const submitButton = form.querySelector('[type="submit"]');
            const feedback = form.querySelector("[data-form-feedback]");
            const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
            const payload = Object.fromEntries(new FormData(form).entries());
            delete payload.csrfmiddlewaretoken;

            if (submitButton) submitButton.disabled = true;
            if (feedback) {
                feedback.textContent = "Submitting...";
                feedback.dataset.state = "pending";
            }

            try {
                const endpoint = new URL(form.dataset.apiEndpoint, `${apiBase}/`);
                const response = await fetch(endpoint, {
                    method: form.method.toUpperCase(),
                    headers: {
                        Accept: "application/json",
                        "Content-Type": "application/json",
                        ...(csrfInput ? { "X-CSRFToken": csrfInput.value } : {}),
                    },
                    credentials: "include",
                    body: JSON.stringify(payload),
                });
                const result = await response.json().catch(() => ({}));

                if (!response.ok) {
                    const validationText = result.errors
                        ? Object.values(result.errors).flat().join(" ")
                        : result.detail || result.message;
                    throw new Error(validationText || `Request failed (${response.status}).`);
                }

                if (feedback) {
                    feedback.textContent = result.message || "Your request was received.";
                    feedback.dataset.state = "success";
                }
                form.reset();
            } catch (error) {
                if (feedback) {
                    feedback.textContent = error.message || "The service could not be reached. Please try again.";
                    feedback.dataset.state = "error";
                }
            } finally {
                if (submitButton) submitButton.disabled = false;
            }
        });
    });
})();