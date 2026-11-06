package timeline

import (
	"fmt"
	"sort"
)

// An instantaneous block owns its millisecond too; durations use [start, end).
func occupiedEnd(b Block) int64 { return b.AtMS + max(1, b.DurationMS) }

func orderedBlocks(t Track) []Block {
	blocks := append([]Block(nil), t.Blocks...)
	sort.SliceStable(blocks, func(i, j int) bool { return blocks[i].AtMS < blocks[j].AtMS })
	return blocks
}

func trackOverlaps(t Track) bool {
	var end int64 = -1
	for _, b := range orderedBlocks(t) {
		if b.AtMS < end {
			return true
		}
		end = occupiedEnd(b)
	}
	return false
}

// SplitTracks moves simultaneous blocks into separate tracks without changing
// IDs, timing, paths, or enabled state. It never modifies the source document.
func SplitTracks(m Definition) (Definition, bool, error) {
	result := m
	result.Tracks = nil
	changed := false
	for _, t := range m.Tracks {
		if !trackOverlaps(t) {
			result.Tracks = append(result.Tracks, t)
			continue
		}
		changed = true
		lanes := []Track{}
		ends := []int64{}
		for _, b := range orderedBlocks(t) {
			index := -1
			for i, end := range ends {
				if b.AtMS >= end {
					index = i
					break
				}
			}
			if index < 0 {
				index = len(lanes)
				lane := Track{ID: t.ID, Name: t.Name, Muted: t.Muted, Blocks: []Block{}}
				if index > 0 {
					lane.ID = NewID("track")
					lane.Name = fmt.Sprintf("%s · %d", t.Name, index+1)
				}
				lanes = append(lanes, lane)
				ends = append(ends, -1)
			}
			lanes[index].Blocks = append(lanes[index].Blocks, b)
			ends[index] = occupiedEnd(b)
		}
		result.Tracks = append(result.Tracks, lanes...)
	}
	if len(result.Tracks) > 64 {
		return m, false, fmt.Errorf("拆分后超过 64 条轨道，请减少同时发生的动作")
	}
	return result, changed, nil
}
