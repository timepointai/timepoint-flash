#!/usr/bin/env node
/**
 * TIMEPOINT Flash - JavaScript/Node.js Client Example
 *
 * Shows how to:
 * 1. Generate a timepoint
 * 2. Stream progress with EventSource (SSE)
 * 3. Fetch results
 *
 * Requirements:
 *   npm install node-fetch eventsource
 *
 * Just run: node javascript_client.js
 */

// For Node.js compatibility
import fetch from 'node-fetch';
import EventSource from 'eventsource';

const API_BASE = 'http://localhost:8000';

/**
 * Create a new timepoint generation request
 */
async function generateTimepoint(query, email = 'dev@example.com') {
  console.log(`🚀 Generating timepoint: '${query}'`);

  const response = await fetch(`${API_BASE}/api/timepoint/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input_query: query,
      requester_email: email
    })
  });

  if (response.status === 429) {
    const data = await response.json();
    console.log('❌ Rate limit exceeded!');
    console.log(data.detail);
    return null;
  }

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();

  console.log(`✅ Started: session_id=${data.session_id}`);
  console.log(`   Slug: ${data.slug}\n`);

  return data;
}

/**
 * Stream progress updates via Server-Sent Events (SSE)
 * Returns a promise that resolves with the slug on success
 */
function streamProgress(sessionId) {
  return new Promise((resolve, reject) => {
    console.log('📡 Streaming progress...\n');

    const url = `${API_BASE}/api/timepoint/status/${sessionId}`;
    const eventSource = new EventSource(url);

    eventSource.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      const { agent, message, progress } = data;

      // Pretty progress bar
      const barLength = 30;
      const filled = Math.floor((barLength * progress) / 100);
      const bar = '█'.repeat(filled) + '░'.repeat(barLength - filled);

      console.log(`[${bar}] ${progress.toString().padStart(3)}% | ${agent.padEnd(12)} | ${message}`);
    });

    eventSource.addEventListener('complete', (e) => {
      const data = JSON.parse(e.data);
      console.log(`\n✅ Complete! Slug: ${data.slug}`);
      eventSource.close();
      resolve(data.slug);
    });

    eventSource.addEventListener('error', (e) => {
      let errorMsg = 'Unknown error';
      try {
        const data = JSON.parse(e.data);
        errorMsg = data.error || errorMsg;
      } catch (err) {
        // If parse fails, use default message
      }
      console.log(`\n❌ Error: ${errorMsg}`);
      eventSource.close();
      reject(new Error(errorMsg));
    });

    eventSource.onerror = (err) => {
      console.log('\n❌ Connection error');
      eventSource.close();
      reject(err);
    };
  });
}

/**
 * Fetch complete timepoint data
 */
async function getTimepointDetails(slug) {
  console.log(`\n📥 Fetching details...`);

  const response = await fetch(`${API_BASE}/api/timepoint/details/${slug}`);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

/**
 * Fetch the latest timepoints (feed)
 */
async function getFeed(limit = 5) {
  console.log(`\n📋 Fetching feed (limit=${limit})...`);

  const response = await fetch(`${API_BASE}/api/feed?limit=${limit}`);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

/**
 * Pretty-print a timepoint summary
 */
function printTimepointSummary(tp) {
  console.log('\n' + '='.repeat(60));
  console.log(`🎬 ${tp.slug}`);
  console.log('='.repeat(60));
  console.log(`Query:        ${tp.input_query}`);
  console.log(`Year:         ${tp.year || 'Unknown'}`);
  console.log(`Season:       ${tp.season || 'Unknown'}`);
  console.log(`Location:     ${tp.location || 'Unknown'}`);
  console.log(`Image URL:    ${tp.image_url || 'N/A'}`);
  console.log(`Characters:   ${tp.character_data_json?.length || 0}`);
  console.log(`Dialog lines: ${tp.dialog_json?.length || 0}`);
  console.log(`Processing:   ${(tp.processing_time_ms / 1000).toFixed(1)}s`);
  console.log('='.repeat(60));
}

/**
 * Main workflow: generate → stream → fetch
 */
async function main() {
  console.log('\n' + '🍌'.repeat(30));
  console.log('TIMEPOINT Flash - JavaScript Client Example');
  console.log('🍌'.repeat(30) + '\n');

  try {
    // Step 1: Generate a timepoint
    const query = 'Victorian London street, foggy evening 1888';
    const result = await generateTimepoint(query);

    if (!result) {
      return;
    }

    const { session_id, slug: initialSlug } = result;

    // Step 2: Stream progress in real-time
    const slug = await streamProgress(session_id);

    // Step 3: Fetch complete results
    const timepoint = await getTimepointDetails(slug);
    printTimepointSummary(timepoint);

    // Optional: Show characters
    if (timepoint.character_data_json?.length > 0) {
      console.log('\n👥 Characters:');
      timepoint.character_data_json.forEach((char) => {
        console.log(`  - ${char.name || 'Unknown'}: ${char.role || 'N/A'}`);
      });
    }

    // Optional: Show dialog (first 3 lines)
    if (timepoint.dialog_json?.length > 0) {
      console.log('\n💬 Dialog:');
      timepoint.dialog_json.slice(0, 3).forEach((line) => {
        console.log(`  ${line.character || '???'}: "${line.text || ''}"`);
      });
    }

    console.log('\n✨ Done! Visit the gallery: http://localhost:8000/');
  } catch (err) {
    if (err.code === 'ECONNREFUSED') {
      console.log('\n❌ Error: Could not connect to server');
      console.log('   Make sure the server is running: ./tp serve');
    } else {
      console.log(`\n❌ Error: ${err.message}`);
    }
  }
}

// Run the example
main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
