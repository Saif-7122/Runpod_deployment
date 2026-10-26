# Making reels: guide for the editing team

You do not need any coding. Everything runs from one web form.

## Every day

1. **Start the pod** (RunPod → Pods → *Content Engine* → **Start**). Ask the admin if you don't have access.
2. In the pod, open **Connect → Web Terminal** and paste:
   ```
   bash /workspace/start.sh
   ```
   It prints a link like `https://xxxx-5678.proxy.runpod.net/form/oxygen-forest-reels`. Bookmark it.
3. Open the link, fill in the form, press **Submit**:
   - **How many videos?** e.g. 10 (about 50 can be made per hour)
   - **Language:** English, Telugu, Hindi, or a mix (videos alternate between the chosen languages)
   - **Style:** Weekend home (more styles coming)
   - **New clips added to Drive since last time?** choose *Yes* only when new footage was uploaded
4. Videos appear in the **Drive OUTPUT folder** as they finish. Each video has:
   - the `.mp4` reel (9:16, 30-40 s, captions, end card)
   - a `- caption.txt` with the Instagram/Facebook post caption and hashtags
   - a `- project.json` (shot list and timings, if you want to re-edit by hand)
5. **Stop the pod** when you are done (RunPod → Stop). It is billed by the hour.

## Good to know

- Only videos that pass the quality checks are uploaded, so a request for 10 can give slightly fewer.
- Do not run two forms at the same time; wait for the first batch to finish (it shows up in Drive).
- New footage: put it in the Footage folder or the OXYGEN FOREST CLIENT folder in Drive, then answer **Yes** to "New clips added".
- Something looks wrong? Send the admin the file `/workspace/data/last_run.log` (Web Terminal: `tail -50 /workspace/data/last_run.log`).
