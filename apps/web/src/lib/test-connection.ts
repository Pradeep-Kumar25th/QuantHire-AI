/**
 * Test Backend Connection
 * =======================
 * Simple utility to test backend connectivity
 */

import axios from 'axios';

const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_URL = baseUrl.endsWith('/api') ? baseUrl : `${baseUrl}/api`;

export async function testBackendConnection() {
  console.log('🧪 Testing backend connection...');
  console.log('📍 Base URL:', baseUrl);
  console.log('📍 API URL:', API_URL);
  
  const tests = [
    {
      name: 'Health Check',
      url: `${baseUrl}/api/health`,
      method: 'GET',
    },
    {
      name: 'JD Generation Test Endpoint',
      url: `${API_URL}/v1/jd-generation/test`,
      method: 'GET',
    },
  ];
  
  for (const test of tests) {
    try {
      console.log(`\n🔍 Testing: ${test.name}`);
      console.log(`   URL: ${test.url}`);
      
      const response = await axios({
        method: test.method as any,
        url: test.url,
        timeout: 5000,
        validateStatus: () => true, // Accept all status codes
      });
      
      console.log(`   ✅ Status: ${response.status}`);
      console.log(`   📦 Data:`, response.data);
      
      if (response.status >= 200 && response.status < 300) {
        console.log(`   ✅ ${test.name} - SUCCESS`);
      } else {
        console.log(`   ⚠️ ${test.name} - Status ${response.status}`);
      }
    } catch (error: any) {
      console.error(`   ❌ ${test.name} - FAILED:`, {
        message: error.message,
        code: error.code,
        hasResponse: !!error.response,
        status: error.response?.status,
      });
    }
  }
}

