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
            form.querySelectorAll('[aria-invalid="true"]').forEach((input) => {
                input.removeAttribute("aria-invalid");
            });
            form.querySelectorAll('input[type="checkbox"][name]').forEach((input) => {
                payload[input.name] = input.checked;
            });
            form.querySelectorAll('input[type="number"][name]').forEach((input) => {
                if (input.value !== "") payload[input.name] = Number(input.value);
            });
            form.querySelectorAll('select[name="storage_capacity_available"]').forEach((select) => {
                payload[select.name] = select.value === "true";
            });

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

                if (!response.ok) {
                    const isLocalFallback = [404, 405].includes(response.status);
                    if (isLocalFallback) {
                        form.submit();
                        return;
                    }

                    const contentType = response.headers.get("content-type") || "";
                    let result = {};
                    if (contentType.includes("application/json")) {
                        try {
                            result = await response.json();
                        } catch {
                            result = {};
                        }
                    }
                    if (!result || typeof result !== "object" || Array.isArray(result)) result = {};
                    const validationText = [];
                    if (typeof result.detail === "string") validationText.push(result.detail);
                    if (typeof result.message === "string") validationText.push(result.message);
                    if (result.errors && typeof result.errors === "object" && !Array.isArray(result.errors)) {
                        Object.entries(result.errors).forEach(([field, messages]) => {
                            const fieldMessages = Array.isArray(messages) ? messages : [messages];
                            const fieldInput = Array.from(form.elements).find((input) => input.name === field);
                            if (fieldInput) fieldInput.setAttribute("aria-invalid", "true");
                            validationText.push(`${field}: ${fieldMessages.join(" ")}`);
                        });
                    }
                    throw new Error(validationText.join(" ") || `Request failed (${response.status}).`);
                }

                const contentType = response.headers.get("content-type") || "";
                let result = {};
                if (response.status !== 204) {
                    if (!contentType.includes("application/json")) {
                        throw new Error(
                            "The service accepted the request but returned an unreadable response. Check its status before trying again."
                        );
                    }
                    try {
                        result = await response.json();
                    } catch {
                        throw new Error(
                            "The service accepted the request but returned invalid JSON. Check its status before trying again."
                        );
                    }
                    if (!result || typeof result !== "object" || Array.isArray(result)) {
                        throw new Error(
                            "The service accepted the request but returned an invalid response. Check its status before trying again."
                        );
                    }
                }
                if (feedback) {
                    feedback.textContent = typeof result.message === "string"
                        ? result.message
                        : "Your request was received.";
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