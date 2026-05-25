const form = document.getElementById("analyze-form");
const analyzeButton = document.getElementById("analyze-button");
const loadingOverlay = document.getElementById("loading-overlay");
const loadingMessage = document.getElementById("loading-message");

const loadingMessages = [
    "Reading resume details...",
    "Comparing skills with the selected role...",
    "Checking job description alignment...",
    "Creating interview questions...",
    "Preparing your ATS report...",
];

if (form && analyzeButton && loadingOverlay && loadingMessage) {
    form.addEventListener("submit", () => {
        if (!form.checkValidity()) {
            return;
        }

        let messageIndex = 0;

        analyzeButton.disabled = true;
        analyzeButton.textContent = "Analyzing...";
        loadingOverlay.setAttribute("aria-hidden", "false");
        document.body.classList.add("is-analyzing");

        loadingMessage.textContent = loadingMessages[messageIndex];

        window.setInterval(() => {
            messageIndex = (messageIndex + 1) % loadingMessages.length;
            loadingMessage.textContent = loadingMessages[messageIndex];
        }, 1800);
    });
}
