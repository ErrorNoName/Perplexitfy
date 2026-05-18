package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"perplexify-go-tui/internal/ui"
)

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "--help", "-h", "help":
			fmt.Println("Perplexify Go TUI")
			fmt.Println()
			fmt.Println("Usage:")
			fmt.Println("  perplexify              launch keyboard TUI")
			fmt.Println("  perplexify --help       show this help")
			fmt.Println()
			fmt.Println("Keys:")
			fmt.Println("  up/down or j/k  move")
			fmt.Println("  enter           select / submit")
			fmt.Println("  esc             back")
			fmt.Println("  tab             switch focus")
			fmt.Println("  q or ctrl+c     quit")
			return
		}
	}

	program := tea.NewProgram(
		ui.NewApp(),
		tea.WithAltScreen(),
	)
	if _, err := program.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Perplexify failed: %v\n", err)
		os.Exit(1)
	}
}
