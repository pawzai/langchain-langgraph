package com.example.investigator.web;

import java.util.List;

import com.example.investigator.domain.ApprovalRequest;
import com.example.investigator.domain.InvestigateRequest;
import com.example.investigator.domain.InvestigationResult;
import com.example.investigator.service.HealthCheckService;
import com.example.investigator.service.InvestigationService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

/** Serves the demo UI. The JSON API lives in {@link InvestigationApiController}. */
@Controller
public class InvestigationController {

    /** Offered as one-click buttons so a demo does not depend on typing accurately. */
    static final List<Scenario> SCENARIOS = List.of(
            new Scenario("Stuck shipment",
                    "Why is shipment SHP-1007 stuck in CREATED status?",
                    "Full investigation across all three sources"),
            new Scenario("Dispatch rules",
                    "What conditions must be met before a shipment can be marked READY_FOR_DISPATCH?",
                    "Documentation only, so it takes the short path"),
            new Scenario("Request a fix",
                    "Fix shipment SHP-1007 so it can be dispatched.",
                    "Stops at the approval gate before anything is applied"),
            new Scenario("Trailer in maintenance",
                    "Why can't shipment SHP-1010 be dispatched?",
                    "A different cause: the trailer is in MAINTENANCE"),
            new Scenario("Inbound-only facility",
                    "Why is shipment SHP-1013 not moving?",
                    "A third cause: BOI does not allow outbound"));

    public record Scenario(String title, String question, String note) {}

    private final InvestigationService investigationService;
    private final HealthCheckService healthCheckService;

    public InvestigationController(InvestigationService investigationService,
                                   HealthCheckService healthCheckService) {
        this.investigationService = investigationService;
        this.healthCheckService = healthCheckService;
    }

    @GetMapping("/")
    public String index(Model model) {
        model.addAttribute("scenarios", SCENARIOS);
        model.addAttribute("question", "");
        model.addAttribute("fast", false);
        return "investigate";
    }

    @PostMapping("/investigate")
    public String investigate(@RequestParam String question,
                              @RequestParam(defaultValue = "false") boolean fast,
                              Model model) {
        model.addAttribute("scenarios", SCENARIOS);
        model.addAttribute("question", question);
        model.addAttribute("fast", fast);

        if (question == null || question.isBlank()) {
            model.addAttribute("error", "Enter a question, or pick one of the scenarios above.");
            return "investigate";
        }

        try {
            InvestigationResult result =
                    investigationService.investigate(new InvestigateRequest(question, null, fast));
            model.addAttribute("result", result);
        } catch (RuntimeException ex) {
            model.addAttribute("error", friendly(ex));
        }
        return "investigate";
    }

    @PostMapping("/approve")
    public String approve(@RequestParam String threadId,
                          @RequestParam String decision,
                          @RequestParam(defaultValue = "") String modifiedAction,
                          @RequestParam(defaultValue = "") String question,
                          @RequestParam(defaultValue = "false") boolean fast,
                          Model model) {
        model.addAttribute("scenarios", SCENARIOS);
        model.addAttribute("question", question);
        model.addAttribute("fast", fast);

        String effective = "modify".equals(decision) ? modifiedAction : decision;
        if ("modify".equals(decision) && modifiedAction.isBlank()) {
            model.addAttribute("error", "Describe the action you want instead, then submit again.");
            return "investigate";
        }

        try {
            model.addAttribute("result",
                    investigationService.resume(new ApprovalRequest(threadId, effective)));
        } catch (RuntimeException ex) {
            model.addAttribute("error", friendly(ex));
        }
        return "investigate";
    }

    @GetMapping("/health/checks")
    public String healthChecks(Model model) {
        model.addAttribute("report", healthCheckService.run());
        return "health";
    }

    private static String friendly(RuntimeException ex) {
        String message = ex.getMessage() == null ? ex.toString() : ex.getMessage();
        if (message.contains("Connection refused") || message.contains("ConnectException")) {
            return "Could not reach Ollama at localhost:11434. Start it with 'ollama serve'.";
        }
        return message;
    }
}
