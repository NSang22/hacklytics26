/**
 * ChunkedGameRecorder — captures Canvas.captureStream() into 15-second
 * .webm chunks and uploads each to the backend immediately on completion.
 *
 * Usage:
 *   const recorder = new ChunkedGameRecorder(canvas, sessionId, apiEndpoint);
 *   recorder.start();
 *   // ... gameplay ...
 *   recorder.stop();   // finalises last partial chunk
 */
class ChunkedGameRecorder {
    constructor(canvas, sessionId, uploadEndpoint, chunkDurationMs = 15000) {
        this.canvas = canvas;
        this.sessionId = sessionId;
        this.uploadEndpoint = uploadEndpoint;
        this.chunkDurationMs = chunkDurationMs;
        this.chunkIndex = 0;
        this.chunks = [];
        this.mediaRecorder = null;
        this.intervalId = null;
        this.active = false;
    }

    start() {
        const stream = this.canvas.captureStream(30); // 30 FPS
        this.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'video/webm;codecs=vp9',
            videoBitsPerSecond: 1_500_000,
        });

        this.chunks = [];
        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                this.chunks.push(e.data);
            }
        };

        this.mediaRecorder.onstop = () => {
            // Upload whatever we have
            if (this.chunks.length > 0) {
                this._uploadChunk(new Blob(this.chunks, { type: 'video/webm' }), this.chunkIndex);
                this.chunkIndex++;
                this.chunks = [];
            }
        };

        // Every chunkDurationMs: stop the current recording, start a new one
        this.mediaRecorder.start();
        this.active = true;

        this.intervalId = setInterval(() => {
            if (this.active && this.mediaRecorder.state === 'recording') {
                this.mediaRecorder.stop();
                // Restart after a tiny delay to let onstop fire
                setTimeout(() => {
                    if (this.active) {
                        this.mediaRecorder.start();
                    }
                }, 50);
            }
        }, this.chunkDurationMs);
    }

    stop() {
        this.active = false;
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
    }

    async _uploadChunk(blob, index) {
        const formData = new FormData();
        formData.append('chunk_index', index.toString());
        formData.append('file', blob, `chunk_${index}.webm`);

        try {
            const resp = await fetch(
                `${this.uploadEndpoint}/v1/sessions/${this.sessionId}/upload-chunk`,
                { method: 'POST', body: formData }
            );
            const data = await resp.json();
            console.log(`[ChunkedRecorder] Chunk ${index} uploaded:`, data);
        } catch (err) {
            console.error(`[ChunkedRecorder] Chunk ${index} upload failed:`, err);
        }
    }

    getChunkCount() {
        return this.chunkIndex;
    }
}
