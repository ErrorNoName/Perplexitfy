package backend

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

type Source struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Snippet string `json:"snippet"`
	Host    string `json:"host"`
}

type Result struct {
	OK             bool     `json:"ok"`
	Mode           string   `json:"mode"`
	Query          string   `json:"query"`
	Answer         string   `json:"answer"`
	Sources        []Source `json:"sources"`
	ModelRequested string   `json:"model_requested"`
	ModelUsed      string   `json:"model_used"`
	Status         string   `json:"status"`
	ElapsedMS      int      `json:"elapsed_ms"`
	Error          string   `json:"error"`
}

type Status struct {
	OK                bool   `json:"ok"`
	CookieConfigured  bool   `json:"cookie_configured"`
	CookieSource      string `json:"cookie_source"`
	Cookie            string `json:"cookie"`
	Session           string `json:"session"`
	User              string `json:"user"`
	Subscription      string `json:"subscription"`
	RemainingPro      *int   `json:"remaining_pro"`
	RemainingResearch *int   `json:"remaining_research"`
	RemainingLabs     *int   `json:"remaining_labs"`
	Error             string `json:"error"`
}

type Client struct {
	PythonExe    string
	WorkingDir   string
	PythonPath   string
	ScriptPath   string
	Timeout      time.Duration
	DefaultModel string
}

func NewClient() Client {
	pythonExe := os.Getenv("PERPLEXIFY_PYTHON")
	if pythonExe == "" {
		pythonExe = "python"
	}
	root, script := detectBackendRoot()
	return Client{
		PythonExe:    pythonExe,
		WorkingDir:   root,
		PythonPath:   buildPythonPath(root),
		ScriptPath:   script,
		Timeout:      140 * time.Second,
		DefaultModel: "sonar",
	}
}

func (c Client) Ask(ctx context.Context, mode, query, model, contextText string) (Result, error) {
	if strings.TrimSpace(query) == "" {
		return Result{OK: false, Mode: mode, Error: "Query is empty"}, nil
	}
	if model == "" {
		model = c.DefaultModel
	}

	timeout := c.Timeout
	if timeout <= 0 {
		timeout = 140 * time.Second
	}
	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	args := c.pythonArgs("json",
		"--mode", mode,
		"--query", query,
		"--model", model,
	)
	if strings.TrimSpace(contextText) != "" {
		args = append(args, "--context", contextText)
	}

	cmd := exec.CommandContext(runCtx, c.PythonExe, args...)
	cmd.Dir = c.WorkingDir
	cmd.Env = os.Environ()
	if c.PythonPath != "" {
		cmd.Env = append(cmd.Env, "PYTHONPATH="+c.PythonPath)
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		if errors.Is(runCtx.Err(), context.DeadlineExceeded) {
			return Result{OK: false, Mode: mode, Error: "Perplexify backend timed out"}, nil
		}
		if parsed, parseErr := parseResult(stdout.Bytes()); parseErr == nil {
			return parsed, nil
		}
		message := strings.TrimSpace(stderr.String())
		if message == "" {
			message = err.Error()
		}
		return Result{OK: false, Mode: mode, Error: message}, nil
	}

	result, err := parseResult(stdout.Bytes())
	if err != nil {
		return Result{OK: false, Mode: mode, Error: "Could not parse backend JSON"}, fmt.Errorf("%w: %s", err, stdout.String())
	}
	return result, nil
}

func parseResult(raw []byte) (Result, error) {
	var result Result
	if err := json.Unmarshal(raw, &result); err != nil {
		return Result{}, err
	}
	return result, nil
}

func (c Client) Status(ctx context.Context) (Status, error) {
	runCtx, cancel := context.WithTimeout(ctx, 45*time.Second)
	defer cancel()

	cmd := exec.CommandContext(runCtx, c.PythonExe, c.pythonArgs("status-json")...)
	cmd.Dir = c.WorkingDir
	cmd.Env = os.Environ()
	if c.PythonPath != "" {
		cmd.Env = append(cmd.Env, "PYTHONPATH="+c.PythonPath)
	}
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	var status Status
	if parseErr := json.Unmarshal(stdout.Bytes(), &status); parseErr != nil {
		return Status{OK: false, Error: strings.TrimSpace(stderr.String())}, parseErr
	}
	return status, err
}

func buildPythonPath(root string) string {
	if root == "" {
		return ""
	}
	parts := []string{root, filepath.Dir(root)}
	if current := os.Getenv("PYTHONPATH"); current != "" {
		parts = append(parts, current)
	}
	return strings.Join(parts, string(os.PathListSeparator))
}

func (c Client) pythonArgs(command string, extra ...string) []string {
	if c.ScriptPath != "" {
		args := []string{c.ScriptPath, command}
		return append(args, extra...)
	}
	args := []string{"cli.py", command}
	return append(args, extra...)
}

func detectBackendRoot() (string, string) {
	candidates := candidateDirs()
	for _, start := range candidates {
		for dir := start; dir != filepath.Dir(dir); dir = filepath.Dir(dir) {
			localScript := filepath.Join(dir, "cli.py")
			if exists(localScript) {
				return dir, localScript
			}
		}
	}
	return ".", ""
}

func candidateDirs() []string {
	var dirs []string
	if wd, err := os.Getwd(); err == nil {
		dirs = append(dirs, wd)
	}
	if exe, err := os.Executable(); err == nil {
		dirs = append(dirs, filepath.Dir(exe))
	}
	return dirs
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
