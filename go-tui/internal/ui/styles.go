package ui

import "github.com/charmbracelet/lipgloss"

var (
	coral      = lipgloss.Color("#ff7a4d")
	orangeDim  = lipgloss.Color("#c86f55")
	black      = lipgloss.Color("#101010")
	panelBlack = lipgloss.Color("#171717")
	softWhite  = lipgloss.Color("#f2eee8")
	muted      = lipgloss.Color("#8b8580")
	line       = lipgloss.Color("#3a302c")
	cyan       = lipgloss.Color("#67d8ef")
	red        = lipgloss.Color("#ff5c7a")

	appStyle = lipgloss.NewStyle().
			Foreground(softWhite).
			Background(black).
			Padding(1, 1)

	titleStyle = lipgloss.NewStyle().
			Foreground(coral).
			Bold(true).
			MarginBottom(1)

	panelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(line).
			Background(panelBlack).
			Padding(1, 1)

	activePanelStyle = panelStyle.Copy().
				BorderForeground(coral)

	mutedStyle = lipgloss.NewStyle().
			Foreground(muted)

	accentStyle = lipgloss.NewStyle().
			Foreground(coral).
			Bold(true)

	infoStyle = lipgloss.NewStyle().
			Foreground(cyan)

	errorStyle = lipgloss.NewStyle().
			Foreground(red).
			Bold(true)

	inputStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder()).
			BorderForeground(line).
			Padding(0, 1)

	selectedItemStyle = lipgloss.NewStyle().
				Foreground(coral).
				Bold(true)

	itemStyle = lipgloss.NewStyle().
			Foreground(softWhite)
)

const logo = `
 ____                 _           _  __
|  _ \ ___ _ __ _ __ | | _____  _(_)/ _|_   _
| |_) / _ \ '__| '_ \| |/ _ \ \/ / | |_| | | |
|  __/  __/ |  | |_) | |  __/>  <| |  _| |_| |
|_|   \___|_|  | .__/|_|\___/_/\_\_|_|  \__, |
               |_|                      |___/
`

const compactLogo = `
Perplexify CLI
Reverse Web Search
`
