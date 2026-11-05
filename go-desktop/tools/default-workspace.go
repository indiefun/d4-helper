//go:build ignore

// Build helper only; the studio creates its own fresh default on first launch.
package main

import (
 "encoding/json"
 "os"
 "github.com/indiefun/d4-helper/go-desktop/internal/timeline"
)
func main(){b,err:=json.MarshalIndent(timeline.Default(),"","  ");if err!=nil{panic(err)};if err:=os.WriteFile(os.Args[1],append(b,'\n'),0644);err!=nil{panic(err)}}
