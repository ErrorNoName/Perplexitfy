package ui

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"perplexify-go-tui/internal/backend"
)

type screen int

const (
	screenHome screen = iota
	screenSearch
	screenChat
	screenStatus
	screenSettings
)

type queryDoneMsg struct {
	mode   string
	result backend.Result
	err    error
}

type statusDoneMsg struct {
	status backend.Status
	err    error
}

type App struct {
	client backend.Client

	width  int
	height int
	screen screen

	menu       []string
	menuIndex  int
	models     []string
	modelIndex int

	searchInput textinput.Model
	chatInput   textinput.Model

	loading      bool
	loadingFrame int
	loadingLabel string

	searchResult *backend.Result
	chatMessages []chatMessage
	statusData   *backend.Status
	lastError    string
}

type chatMessage struct {
	Role    string
	Content string
	Sources []backend.Source
}

func NewApp() App {
	search := textinput.New()
	search.Placeholder = "Ask Perplexify to search the web..."
	search.CharLimit = 500
	search.Width = 72

	chat := textinput.New()
	chat.Placeholder = "Message Perplexify..."
	chat.CharLimit = 500
	chat.Width = 72

	return App{
		client:       backend.NewClient(),
		screen:       screenHome,
		menu:         []string{"Search", "Chat", "Status", "Settings", "Quit"},
		models:       []string{"sonar", "sonar-pro", "gpt", "claude"},
		searchInput:  search,
		chatInput:    chat,
		loadingLabel: "Perplexifying",
	}
}

func (a App) Init() tea.Cmd {
	return textinput.Blink
}

func (a App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		a.width = msg.Width
		a.height = msg.Height
		a.searchInput.Width = clamp(a.contentWidth()-8, 20, 96)
		a.chatInput.Width = clamp(a.contentWidth()-8, 20, 96)
		return a, nil
	case tea.KeyMsg:
		return a.handleKey(msg)
	case queryDoneMsg:
		a.loading = false
		if msg.err != nil {
			a.lastError = msg.err.Error()
			return a, nil
		}
		if !msg.result.OK && msg.result.Error != "" {
			a.lastError = msg.result.Error
		}
		if msg.mode == "search" {
			a.searchResult = &msg.result
		} else {
			a.chatMessages = append(a.chatMessages, chatMessage{
				Role:    "Perplexify",
				Content: msg.result.Answer,
				Sources: msg.result.Sources,
			})
		}
		return a, nil
	case statusDoneMsg:
		a.loading = false
		a.statusData = &msg.status
		if msg.err != nil {
			a.lastError = msg.err.Error()
		}
		return a, nil
	case tickMsg:
		if a.loading {
			a.loadingFrame++
			return a, tick()
		}
		return a, nil
	}

	var cmd tea.Cmd
	if a.screen == screenSearch {
		a.searchInput, cmd = a.searchInput.Update(msg)
	}
	if a.screen == screenChat {
		a.chatInput, cmd = a.chatInput.Update(msg)
	}
	return a, cmd
}

func (a App) View() string {
	body := ""
	switch a.screen {
	case screenHome:
		body = a.viewHome()
	case screenSearch:
		body = a.viewSearch()
	case screenChat:
		body = a.viewChat()
	case screenStatus:
		body = a.viewStatus()
	case screenSettings:
		body = a.viewSettings()
	}
	help := mutedStyle.Render("up/down or j/k move  enter select/submit  esc back  tab focus  q quit")
	return appStyle.Width(a.contentWidth()).Render(body + "\n\n" + wrapText(help, a.contentWidth()))
}

func (a App) handleKey(msg tea.KeyMsg) (App, tea.Cmd) {
	if a.isTypingKey(msg) {
		switch a.screen {
		case screenSearch:
			return a.handleSearchKey(msg)
		case screenChat:
			return a.handleChatKey(msg)
		}
	}

	switch msg.String() {
	case "ctrl+c":
		return a, tea.Quit
	case "q":
		if a.screen == screenHome {
			return a, tea.Quit
		}
		a.screen = screenHome
		a.lastError = ""
		return a, nil
	case "esc":
		a.screen = screenHome
		a.lastError = ""
		return a, nil
	}

	if a.loading {
		return a, nil
	}

	switch a.screen {
	case screenHome:
		return a.handleHomeKey(msg)
	case screenSearch:
		return a.handleSearchKey(msg)
	case screenChat:
		return a.handleChatKey(msg)
	case screenStatus:
		if msg.String() == "r" || msg.String() == "enter" {
			return a.startStatus()
		}
	case screenSettings:
		return a.handleSettingsKey(msg)
	}
	return a, nil
}

func (a App) handleHomeKey(msg tea.KeyMsg) (App, tea.Cmd) {
	switch msg.String() {
	case "up", "k":
		a.menuIndex = wrap(a.menuIndex-1, len(a.menu))
	case "down", "j":
		a.menuIndex = wrap(a.menuIndex+1, len(a.menu))
	case "enter":
		switch a.menu[a.menuIndex] {
		case "Search":
			a.screen = screenSearch
			a.searchInput.Focus()
			return a, textinput.Blink
		case "Chat":
			a.screen = screenChat
			a.chatInput.Focus()
			return a, textinput.Blink
		case "Status":
			a.screen = screenStatus
			return a.startStatus()
		case "Settings":
			a.screen = screenSettings
		case "Quit":
			return a, tea.Quit
		}
	}
	return a, nil
}

func (a App) isTypingKey(msg tea.KeyMsg) bool {
	if a.loading {
		return false
	}
	if a.screen != screenSearch && a.screen != screenChat {
		return false
	}
	key := msg.String()
	switch key {
	case "ctrl+c", "esc", "enter", "up", "down", "left", "right", "tab", "shift+tab":
		return false
	}
	return true
}

func (a App) handleSearchKey(msg tea.KeyMsg) (App, tea.Cmd) {
	if msg.String() == "enter" {
		query := strings.TrimSpace(a.searchInput.Value())
		if query == "" {
			a.lastError = "Write a search query first."
			return a, nil
		}
		a.lastError = ""
		a.loading = true
		a.loadingLabel = "Skedaddling across sources"
		a.searchResult = nil
		return a, tea.Batch(tick(), a.runQuery("search", query, ""))
	}
	var cmd tea.Cmd
	a.searchInput, cmd = a.searchInput.Update(msg)
	return a, cmd
}

func (a App) handleChatKey(msg tea.KeyMsg) (App, tea.Cmd) {
	if msg.String() == "enter" {
		query := strings.TrimSpace(a.chatInput.Value())
		if query == "" {
			a.lastError = "Write a message first."
			return a, nil
		}
		a.lastError = ""
		a.chatMessages = append(a.chatMessages, chatMessage{Role: "You", Content: query})
		a.chatInput.SetValue("")
		a.loading = true
		a.loadingLabel = "Thinking locally"
		return a, tea.Batch(tick(), a.runQuery("chat", query, a.chatContext()))
	}
	var cmd tea.Cmd
	a.chatInput, cmd = a.chatInput.Update(msg)
	return a, cmd
}

func (a App) handleSettingsKey(msg tea.KeyMsg) (App, tea.Cmd) {
	switch msg.String() {
	case "up", "k", "left", "h":
		a.modelIndex = wrap(a.modelIndex-1, len(a.models))
	case "down", "j", "right", "l":
		a.modelIndex = wrap(a.modelIndex+1, len(a.models))
	}
	return a, nil
}

func (a App) startStatus() (App, tea.Cmd) {
	a.loading = true
	a.loadingLabel = "Checking session"
	a.statusData = nil
	a.lastError = ""
	return a, tea.Batch(tick(), func() tea.Msg {
		status, err := a.client.Status(context.Background())
		return statusDoneMsg{status: status, err: err}
	})
}

func (a App) runQuery(mode, query, contextText string) tea.Cmd {
	model := a.models[a.modelIndex]
	return func() tea.Msg {
		result, err := a.client.Ask(context.Background(), mode, query, model, contextText)
		return queryDoneMsg{mode: mode, result: result, err: err}
	}
}

func (a App) chatContext() string {
	var lines []string
	start := 0
	if len(a.chatMessages) > 8 {
		start = len(a.chatMessages) - 8
	}
	for _, msg := range a.chatMessages[start:] {
		lines = append(lines, fmt.Sprintf("%s: %s", msg.Role, msg.Content))
	}
	return strings.Join(lines, "\n")
}

func (a App) viewHome() string {
	var items []string
	for i, item := range a.menu {
		prefix := "  "
		style := itemStyle
		if i == a.menuIndex {
			prefix = "> "
			style = selectedItemStyle
		}
		items = append(items, style.Render(prefix+item))
	}
	contentWidth := a.contentWidth()
	logoText := logo
	if contentWidth < 72 {
		logoText = compactLogo
	}
	leftBody := titleStyle.Render("Perplexify") + "\n" +
		accentStyle.Render(logoText) + "\n" +
		mutedStyle.Render("Reverse Perplexity, terminal-first.") + "\n" +
		mutedStyle.Render("Model: ") + infoStyle.Render(a.models[a.modelIndex])
	rightBody := accentStyle.Render("Menu") + "\n\n" +
		strings.Join(items, "\n") + "\n\n" +
		mutedStyle.Render("Perplexity research, wrapped in a sharp terminal cockpit.")
	if contentWidth < 92 {
		return renderPanel(activePanelStyle, contentWidth, leftBody) + "\n" +
			renderPanel(panelStyle, contentWidth, rightBody)
	}
	leftWidth := clamp(contentWidth-38, 44, 62)
	rightWidth := contentWidth - leftWidth - 2
	left := renderPanel(activePanelStyle, leftWidth,
		leftBody,
	)
	right := renderPanel(panelStyle, rightWidth,
		rightBody,
	)
	return lipgloss.JoinHorizontal(lipgloss.Top, left, "  ", right)
}

func (a App) viewSearch() string {
	contentWidth := a.contentWidth()
	content := accentStyle.Render("Search") + "\n" +
		mutedStyle.Render("Ask, press enter, sources appear below.") + "\n\n" +
		inputStyle.Width(clamp(contentWidth-8, 20, 96)).Render(a.searchInput.View())
	if a.loading {
		content += "\n\n" + a.loader()
	}
	if a.lastError != "" {
		content += "\n\n" + errorStyle.Render(a.lastError)
	}
	if a.searchResult != nil {
		content += "\n\n" + renderResult(*a.searchResult, clamp(contentWidth-10, 28, 100))
	}
	content += "\n\n" + selectedItemStyle.Render("< Back")
	return renderPanel(activePanelStyle, contentWidth, content)
}

func (a App) viewChat() string {
	contentWidth := a.contentWidth()
	messageWidth := clamp(contentWidth-10, 28, 96)
	var lines []string
	lines = append(lines, accentStyle.Render("Chat"))
	lines = append(lines, mutedStyle.Render("A small in-memory conversation. Press enter to send."))
	lines = append(lines, "")
	for _, msg := range a.chatMessages {
		lines = append(lines, renderChatMessage(msg, messageWidth))
	}
	if a.loading {
		lines = append(lines, a.loader())
	}
	if a.lastError != "" {
		lines = append(lines, errorStyle.Render(a.lastError))
	}
	lines = append(lines, "")
	lines = append(lines, inputStyle.Width(clamp(contentWidth-8, 20, 96)).Render(a.chatInput.View()))
	lines = append(lines, "")
	lines = append(lines, selectedItemStyle.Render("< Back"))
	return renderPanel(activePanelStyle, contentWidth, strings.Join(lines, "\n"))
}

func (a App) viewStatus() string {
	contentWidth := a.contentWidth()
	content := accentStyle.Render("Status") + "\n" + mutedStyle.Render("Press r to refresh. Select Back or press esc to return.") + "\n\n"
	if a.loading {
		content += a.loader()
	} else if a.statusData != nil {
		content += renderStatus(*a.statusData, clamp(contentWidth-8, 28, 100))
	} else {
		content += mutedStyle.Render("No status loaded yet.")
	}
	if a.lastError != "" {
		content += "\n\n" + errorStyle.Render(a.lastError)
	}
	content += "\n\n" + selectedItemStyle.Render("< Back")
	return renderPanel(activePanelStyle, contentWidth, content)
}

func (a App) viewSettings() string {
	contentWidth := a.contentWidth()
	var rows []string
	for i, model := range a.models {
		line := "  " + model
		if i == a.modelIndex {
			line = "> " + model
			rows = append(rows, selectedItemStyle.Render(line))
			continue
		}
		rows = append(rows, itemStyle.Render(line))
	}
	return renderPanel(activePanelStyle, contentWidth,
		accentStyle.Render("Settings")+"\n"+
			mutedStyle.Render("Choose model preference with arrows or j/k.")+"\n\n"+
			strings.Join(rows, "\n")+"\n\n"+
			selectedItemStyle.Render("< Back"),
	)
}

func (a App) contentWidth() int {
	if a.width <= 0 {
		return 88
	}
	if a.width < 36 {
		return max(20, a.width-2)
	}
	return clamp(a.width-4, 32, 132)
}

func renderPanel(style lipgloss.Style, totalWidth int, body string) string {
	contentWidth := totalWidth - 4
	if contentWidth < 16 {
		contentWidth = totalWidth
	}
	return style.Width(contentWidth).Render(body)
}

func (a App) loader() string {
	frames := []string{"*", ".*", "..*", "...*", " ..*", "  .*", "   *", "  *.", " *.."}
	frame := frames[a.loadingFrame%len(frames)]
	return accentStyle.Render(frame+" "+a.loadingLabel+"...") + mutedStyle.Render("  esc ignored while running")
}

type tickMsg time.Time

func tick() tea.Cmd {
	return tea.Tick(120*time.Millisecond, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func renderResult(result backend.Result, width int) string {
	answer := strings.TrimSpace(result.Answer)
	if answer == "" {
		answer = result.Error
	}
	meta := mutedStyle.Render(fmt.Sprintf("status=%s  model=%s  %dms", result.Status, result.ModelUsed, result.ElapsedMS))
	var blocks []string
	blocks = append(blocks, meta, wrapText(answer, width))
	if len(result.Sources) > 0 {
		blocks = append(blocks, renderSources(result.Sources, width))
	}
	return strings.Join(blocks, "\n\n")
}

func renderChatMessage(msg chatMessage, width int) string {
	style := panelStyle.Copy().Width(max(20, width-4))
	if strings.EqualFold(msg.Role, "You") {
		style = style.BorderForeground(orangeDim)
	} else {
		style = style.BorderForeground(coral)
	}
	body := accentStyle.Render(msg.Role) + "\n" + wrapText(msg.Content, max(18, width-8))
	if len(msg.Sources) > 0 {
		body += "\n\n" + renderSources(msg.Sources, max(18, width-8))
	}
	return style.Render(body)
}

func renderSources(sources []backend.Source, width int) string {
	var lines []string
	lines = append(lines, accentStyle.Render("Sources"))
	for i, source := range sources {
		title := source.Title
		if strings.HasPrefix(title, "http") {
			title = hostFromURL(source.URL)
		}
		lines = append(lines, fmt.Sprintf("%d. %s\n   %s", i+1, wrapText(title, width-4), infoStyle.Render(wrapText(source.URL, width-4))))
	}
	return strings.Join(lines, "\n")
}

func renderStatus(status backend.Status, width int) string {
	rows := []string{
		accentStyle.Render("Session") + "  " + status.Session,
		accentStyle.Render("User") + "     " + emptyDash(status.User),
		accentStyle.Render("Plan") + "     " + emptyDash(status.Subscription),
		accentStyle.Render("Cookie") + "   " + status.Cookie,
	}
	if status.CookieSource != "" {
		rows = append(rows, accentStyle.Render("Source")+"   "+wrapText(status.CookieSource, width-12))
	}
	rows = append(rows, "")
	rows = append(rows, accentStyle.Render("Limits"))
	rows = append(rows, fmt.Sprintf("  Pro research: %s", intPtrText(status.RemainingPro)))
	rows = append(rows, fmt.Sprintf("  Research:     %s", intPtrText(status.RemainingResearch)))
	rows = append(rows, fmt.Sprintf("  Labs:         %s", intPtrText(status.RemainingLabs)))
	if status.Error != "" {
		rows = append(rows, "", errorStyle.Render(wrapText(status.Error, width)))
	}
	return strings.Join(rows, "\n")
}

func intPtrText(value *int) string {
	if value == nil {
		return "-"
	}
	return fmt.Sprintf("%d", *value)
}

func emptyDash(value string) string {
	if strings.TrimSpace(value) == "" {
		return "-"
	}
	return value
}

func hostFromURL(raw string) string {
	trimmed := strings.TrimPrefix(strings.TrimPrefix(raw, "https://"), "http://")
	parts := strings.SplitN(trimmed, "/", 2)
	return strings.TrimPrefix(parts[0], "www.")
}

func wrapText(s string, width int) string {
	words := strings.Fields(s)
	if len(words) == 0 {
		return ""
	}
	var lines []string
	line := words[0]
	for _, word := range words[1:] {
		if lipgloss.Width(line)+lipgloss.Width(word)+1 > width {
			lines = append(lines, line)
			line = word
		} else {
			line += " " + word
		}
	}
	lines = append(lines, line)
	return strings.Join(lines, "\n")
}

func wrap(index, length int) int {
	if length == 0 {
		return 0
	}
	if index < 0 {
		return length - 1
	}
	if index >= length {
		return 0
	}
	return index
}

func clamp(value, minValue, maxValue int) int {
	if value < minValue {
		return minValue
	}
	if value > maxValue {
		return maxValue
	}
	return value
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
