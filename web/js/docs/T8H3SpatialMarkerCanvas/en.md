# H3 Spatial Marker Canvas

No audio plugin required. Upload/select a still image in this node and click **🖱 手动画框 / Edit spatial regions**.
Add actor and target rectangles by dragging, fill descriptions/colors, add actor→target actions, then Apply and save your workflow.
Select a box to move it or resize with eight handles. Undo/redo, explicit redraw, local pixel-exact output preview and unsaved-close checks are included.
The existing-marked-image mode declares meanings without repainting the uploaded pixels.

marked_image → H3 references; marker_plan → existing Visual Marker Config → H3.visual_marker_config.
The config remains Off until explicitly enabled. Hybrid may connect source_image to its first-frame input.
Configure your enhancer provider separately. No inference happens in the editor or preview.

Coordinates refer to the source, not video trajectories. Single still RGB / 4 MP is the v1 image contract, not a video-duration limit.
Preview and execution share CPU/EXIF/RGB decoding. Apply binds the source RGB digest; changed sources must be reloaded and reviewed.
Connected fields retain ownership: the editor does not disconnect links or write hidden offline values.
Preview reads only the configured Comfy input directory; normal cloud enhancement still transmits reference pixels and marker text.

This plan is for this enhancer, not the audio plugin's exact Python plan class. For downstream audio Prompt/Bind,
rebuild its original Prepare using source_image and markers_json with matching render mode/stroke. No cross-project patch is made.
No marker-removal, physical-path or rendered-video guarantee.
